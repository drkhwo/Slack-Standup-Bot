import os
import logging
import re
import json
from datetime import date, datetime
import random
import time

# Third-party imports
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from supabase import create_client, Client
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Local imports
from phrases import OPENING_PHRASES

# Load environment variables
load_dotenv()

# Configuration
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
VACATION_TRACKER_API_KEY = os.environ.get("VACATION_TRACKER_API_KEY")

# Global state to track the daily thread timestamp
daily_thread_ts = None

# Mapping: Slack User ID -> Name as it appears in Vacation Tracker
TEAM_MAPPING = {
    # == @eng-team ==
    "U02H9RXPKGT": "Alexey Leshchuk",
    "U08SKHD45U2": "Anastasia Kondratyuk",
    "U06A6MV64R2": "andrei",
    "U035U3KTFL5": "Anton Tyutin",
    "U08MW9K5K0U": "Ban Markovic",
    "UEXNGPDTR": "Boris Romanov",
    "U0AD8TDM4DQ": "Constantin Chopin",
    "U097GKF641M": "Cristian Matzov",
    "U085J8B5TJ6": "Ed",
    "U097GKK3UUX": "Georgi Todorov",
    "U011Q8J1PDK": "Georgii Andrianov",
    "U09QE0E0HHQ": "Giorgio Sarno",
    "U088WHYP2P6": "Gvantsa Nebadze",
    "U0965UA3XQ8": "maksim",
    "U08EFQCMJ3U": "Paweł",
    "U09T69U1Y5V": "Sebastian",
    "USMQ8CRU6": "Semyon Vlasov",
    "U04SBH53P9C": "Sergei Mironov",
    "U0821BRMJ4R": "Stan Khvo",
    "U098DPA85PY": "Wojciech Klarowski",
    "U09MF4SB7C2": "Xhonino (John)",
    
    # == @brand-team ==
    "U07SR89J8NA": "Artiom Zverev",
    "U089EU49X7B": "Minju Song",
    
    # == Others ==
    "U068KKKNP9R": "dmytro 'kino' klochko"
}

# Collect all user IDs for report tracking, excluding CEO (@dk - U068KKKNP9R)
TEAM_USER_IDS = [uid for uid in TEAM_MAPPING.keys() if uid != "U068KKKNP9R"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize clients
app = None
supabase = None

VACATION_TRACKER_API_URL = "https://api.vacationtracker.io"

def get_vacation_users():
    """Get users currently on vacation via the Vacation Tracker API."""
    vacation_users = set()

    if not VACATION_TRACKER_API_KEY:
        logger.warning("VACATION_TRACKER_API_KEY not set, skipping vacation check")
        return vacation_users

    today = date.today().isoformat()

    # Reverse mapping: lowercase name -> Slack user ID
    name_to_uid = {name.lower(): uid for uid, name in TEAM_MAPPING.items()}

    try:
        headers = {
            "x-api-key": VACATION_TRACKER_API_KEY,
            "Content-Type": "application/json",
        }

        next_token = None
        page = 0

        while True:
            page += 1
            params = {
                "startDate": today,
                "endDate": today,
                "status": "APPROVED",
                "expand": "user",
            }
            if next_token:
                params["nextToken"] = next_token

            resp = requests.get(
                f"{VACATION_TRACKER_API_URL}/v1/leaves",
                headers=headers,
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            for leave in data.get("data", []):
                # Only count approved leaves
                if leave.get("status") != "APPROVED":
                    continue

                # Try nested user object (API may use "user" or "userUsers")
                user_info = leave.get("user") or leave.get("userUsers") or {}
                user_name = user_info.get("name", "").lower()

                if user_name in name_to_uid:
                    vacation_users.add(name_to_uid[user_name])
                    logger.info(f"Found vacationer (API): {user_info.get('name')}")

            next_token = data.get("nextToken")
            if not next_token:
                break

            # Safety: max 10 pages
            if page >= 10:
                logger.warning("Vacation API: hit pagination limit (10 pages)")
                break

        logger.info(f"Users on vacation today: {vacation_users}")
        return vacation_users

    except requests.exceptions.HTTPError as e:
        logger.error(f"Vacation Tracker API HTTP error: {e.response.status_code} — {e.response.text[:200]}")
        return "error"
    except Exception as e:
        logger.error(f"Error fetching vacations from API: {e}")
        return "error"

def post_daily_thread():
    global daily_thread_ts
    
    if not app or not CHANNEL_ID:
        logger.error("App or CHANNEL_ID not initialized")
        return

    phrase = random.choice(OPENING_PHRASES)
    
    try:
        standup_text = (
            f"{phrase} <!subteam^S074DP77Q9H> <!subteam^S08EJBE5Q4X>\n\n"
            "*Daily — status thread* 💥\n"
            "*Please reply here before the 12:00 sync with:*\n"
            "*Yesterday:* what shipped / merged. Make sure you quote your last reply and update it with statuses.\n"
            "*Today (by EOD or days remaining):* what you'll complete / how many days left\n"
            "*Blockers / Risks:* who/what is needed to unblock\n"
            "*Status-only here; move discussion to subthreads*\n"
            "*If you can't finish something today, state the time remaining*\n\n"
            "cc: <@U068KKKNP9R>"
        )
        response = app.client.chat_postMessage(
            channel=CHANNEL_ID,
            text=standup_text
        )
        daily_thread_ts = response["ts"]
        logger.info(f"Posted daily thread: {daily_thread_ts}")
        
        # Save thread timestamp to database
        if supabase:
            try:
                supabase.table("bot_state").upsert({"key": "daily_thread_ts", "value": daily_thread_ts}).execute()
            except Exception as e:
                logger.warning(f"Could not save bot state: {e}")
        
        # Post vacation status right after the thread
        vacations = get_vacation_users()
        
        if vacations == "error":
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text="⚠️ _Failed to check vacations (channel or API access error)._"
            )
        elif vacations:
            mentions = ", ".join([f"<@{uid}>" for uid in vacations])
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text=f"🌴 *Out today (Vacation/Off):* {mentions}\n_Enjoy your time off!_"
            )
        else:
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text="🌴 *Everyone's in today!* (No one on vacation)"
            )
            
    except Exception as e:
        logger.error(f"Error posting daily thread: {e}")

def check_missing_reports():
    global daily_thread_ts
    if not daily_thread_ts:
        logger.warning("No daily thread found for today. Skipping check.")
        return
    
    if not supabase:
        logger.error("Supabase client not initialized")
        return

    today = date.today().isoformat()
    
    try:
        # 1. Get users who already reported
        response = supabase.table("standup_reports").select("user_id").eq("date", today).execute()
        reported_users = {row["user_id"] for row in response.data}
        
        # 2. Get users on vacation
        vacation_users = get_vacation_users()
        if vacation_users == "error":
            vacation_users = set()  # On error, assume no vacations to avoid breaking the flow

        # 3. Find users who haven't reported (TEAM_USER_IDS already excludes CEO)
        missing_users = [
            uid for uid in TEAM_USER_IDS 
            if uid not in reported_users and uid not in vacation_users
        ]
        
        # 4. Send reminder with a meme
        if missing_users:
            MEMES = [
                "I am once again asking for your daily updates... 🧤",
                "Error 404: Standup reports not found. 🤖",
                "Where is the standup, Lebowski?! 🎳",
                "Git push origin standup_report — waiting for your statuses! 🐙",
                "The 12:00 sync is approaching fast! Drop your updates! ⏳",
                "Houston, we have a problem. Can't see your reports! 🚀"
            ]
            meme = random.choice(MEMES)
            mentions = " ".join([f"<@{uid}>" for uid in missing_users])
            
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text=f"Hey {mentions}! {meme}"
            )
            logger.info(f"Reminded missing users: {missing_users}")
        else:
            logger.info("All active users have reported. No reminders needed!")
            
    except Exception as e:
        logger.error(f"Error checking missing reports: {e}")

def register_events(app_instance):
    @app_instance.event("message")
    def handle_message_events(body, logger):
        global daily_thread_ts
        event = body["event"]
        
        # Check if it's a reply in the daily thread
        if daily_thread_ts and event.get("thread_ts") == daily_thread_ts:
            user_id = event["user"]
            text = event["text"]
            ts = event["ts"]
            today = date.today().isoformat()
            
            # Skip bot messages
            if event.get("bot_id"):
                return

            logger.info(f"Received report from {user_id}")
            
            if not supabase:
                logger.error("Supabase client not initialized, cannot save report")
                return

            try:
                # 1. Check if this user already reported today
                existing_record = supabase.table("standup_reports").select("raw_text").eq("user_id", user_id).eq("date", today).execute()
                
                if existing_record.data:
                    # Report exists — append new text to existing
                    old_text = existing_record.data[0]["raw_text"]
                    final_text = f"{old_text}\n\n[Addition:]:\n{text}"
                    
                    # Update existing record
                    supabase.table("standup_reports").update({"raw_text": final_text}).eq("user_id", user_id).eq("date", today).execute()
                    logger.info(f"Updated existing report for {user_id}")
                else:
                    # No report yet — create new record
                    data = {
                        "user_id": user_id,
                        "date": today,
                        "raw_text": text,
                        "thread_ts": ts
                    }
                    supabase.table("standup_reports").insert(data).execute()
                    logger.info(f"Inserted new report for {user_id}")
                
                # Add checkmark reaction to the message
                app_instance.client.reactions_add(
                    channel=CHANNEL_ID,
                    name="white_check_mark",
                    timestamp=ts
                )
                
            except Exception as e:
                logger.error(f"Error saving report: {e}")

def main():
    global app, supabase, daily_thread_ts
    
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        logger.error("SLACK_BOT_TOKEN or SLACK_APP_TOKEN not set")
        return
        
    app = App(token=SLACK_BOT_TOKEN)
    supabase = get_supabase_client()
    
    register_events(app)

    # Schedule jobs
    scheduler = BackgroundScheduler()
    # Using 'cron' triggers
    scheduler.add_job(post_daily_thread, 'cron', hour=17, minute=19)
    scheduler.add_job(check_missing_reports, 'cron', hour=11, minute=30)
    scheduler.start()
    
    logger.info("Bot started! 🤖")

    # Restore daily_thread_ts from Supabase if available
    if supabase:
        try:
            result = supabase.table("bot_state").select("value").eq("key", "daily_thread_ts").execute()
            if result.data:
                daily_thread_ts = result.data[0]["value"]
                logger.info(f"Restored daily_thread_ts: {daily_thread_ts}")
        except Exception as e:
            logger.warning(f"Could not restore bot state: {e}")

    # -------- TEST LINES --------
    post_daily_thread()
    check_missing_reports()
    # -----------------------------------

    # Start Slack Socket Mode
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    main()