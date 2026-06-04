import os
import logging
import re
from datetime import date, timedelta
import random
from zoneinfo import ZoneInfo

# Third-party imports
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from supabase import create_client
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Local imports
from phrases import get_opening_phrase

# Load environment variables
load_dotenv()

# Configuration
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
ALERT_CHANNEL_ID = os.environ.get("ALERT_CHANNEL_ID")  # Optional: mirror alerts to a test/monitoring channel
VACATION_TRACKER_API_KEY = os.environ.get("VACATION_TRACKER_API_KEY")
SKIP_TODAY = os.environ.get("SKIP_TODAY", "")
PERSONAL_REMINDER_USER_ID = os.environ.get("PERSONAL_REMINDER_USER_ID", "")
LOCAL_TIMEZONE = ZoneInfo("Europe/Paris")

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
    "U0B670M7HU6": "danil levinson",
    "U0B6RSB4M5E": "Vladimir Lesunov",
    
    # == Others ==
    "U068KKKNP9R": "dmytro 'kino' klochko"
}

# Collect all user IDs for report tracking, excluding CEO (@dk - U068KKKNP9R)
TEAM_USER_IDS = [uid for uid in TEAM_MAPPING.keys() if uid != "U068KKKNP9R"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REMINDER_MEMES = [
    "Tiny status update, huge reduction in uncertainty. Please drop yours before 13:00. 📍\nhttps://media.giphy.com/media/QSxLddAZGgYS5OH2i8/giphy.gif",
    "The thread is doing a wellness check on your update. It misses you. 🧵\nhttps://media.giphy.com/media/j4r8T6pi88C7LxFxfz/giphy.gif",
    "Quick async favor: turn today's mystery into a status update. 🔎\nhttps://media.giphy.com/media/BR5Fhn44CUwpmxKuLp/giphy.gif",
    "If the plan changed, the thread should know. Status update time. 🕐\nhttps://media.giphy.com/media/qNl3Zqg5dkhxvRP4Kb/giphy.gif",
    "A brief update now saves a bunch of context hunting later. 🧭\nhttps://media.giphy.com/media/9k70aUGqqXAuQt9RYi/giphy.gif",
    "Please feed the standup thread: yesterday, today, blockers. It runs on clarity. ⚡\nhttps://media.giphy.com/media/QPQ3xlJhqR1BXl89RG/giphy.gif",
]

END_OF_DAY_GIFS = [
    "https://media.giphy.com/media/PMmNA8jtiohoZjvWlC/giphy.gif",
    "https://media.giphy.com/media/L2ePMMz84gG2ntBSG8/giphy.gif",
    "https://media.giphy.com/media/qGK80QKZ77Y8xOQWpj/giphy.gif",
]

THREAD_CLOSED_MESSAGES = [
    "This thread is officially *CLOSED* for today.\nLate updates can wait for tomorrow's thread. Future archaeology avoided. 💙🌅",
    "End of day checkpoint: this standup thread is now *CLOSED*.\nTomorrow gets a fresh thread and a fresh chance to be on time. 💙🌅",
    "Thread closed. Please do not add tomorrow's update here.\nChronology is fragile. Let's protect it. 💙🌅",
    "That's a wrap for today's standup thread.\nIf the update did not make it in, bring it to tomorrow's thread. 💙🌅",
    "Standup thread closed for the day.\nNo new updates here after this point; tomorrow gets its own clean timeline. 💙🌅",
]

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize clients
app = None
supabase = None

VACATION_TRACKER_API_URL = "https://api.vacationtracker.io"


def send_alert(text):
    """Send a short notification to the monitoring/test channel (if configured)."""
    if not app or not ALERT_CHANNEL_ID:
        return
    try:
        app.client.chat_postMessage(channel=ALERT_CHANNEL_ID, text=text)
    except Exception as e:
        logger.warning(f"Could not send alert: {e}")


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


def get_missing_users_today():
    """Return users who still have not posted an update today."""
    if not supabase:
        logger.error("Supabase client not initialized")
        return None

    today = date.today().isoformat()

    response = supabase.table("standup_reports").select("user_id").eq("date", today).execute()
    reported_users = {row["user_id"] for row in response.data}

    vacation_users = get_vacation_users()
    if vacation_users == "error":
        vacation_users = set()

    return [
        uid for uid in TEAM_USER_IDS
        if uid not in reported_users and uid not in vacation_users
    ]

def post_daily_thread():
    global daily_thread_ts

    if not app or not CHANNEL_ID:
        logger.error("App or CHANNEL_ID not initialized")
        return

    phrase = get_opening_phrase()
    
    try:
        # Removed "12:00 sync" mention, kept just the deadline
        standup_text = (
            f"{phrase} <!subteam^S074DP77Q9H> <!subteam^S08EJBE5Q4X>\n\n"
            "*Daily — status thread* 💥\n"
            "*Please reply here before 13:00 with:*\n"
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

        # Alert to monitoring channel
        thread_link = f"https://slack.com/archives/{CHANNEL_ID}/p{daily_thread_ts.replace('.', '')}"
        send_alert(f"✅ Daily standup thread posted → <{thread_link}|open thread>")
        
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
    if SKIP_TODAY == "1":
        logger.info("SKIP_TODAY is set — skipping reminder.")
        return
    if not daily_thread_ts:
        logger.warning("No daily thread found for today. Skipping check.")
        return

    try:
        missing_users = get_missing_users_today()
        if missing_users is None:
            return
        
        # 4. Send reminder with a meme
        if missing_users:
            meme = random.choice(REMINDER_MEMES)
            mentions = " ".join([f"<@{uid}>" for uid in missing_users])
            
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text=f"Hey {mentions}! {meme}"
            )
            logger.info(f"Reminded missing users: {missing_users}")
            send_alert(f"⏰ Reminder sent to {len(missing_users)} people who haven't reported yet")
        else:
            logger.info("All active users have reported. No reminders needed!")
            send_alert("🎉 All team members have reported — no reminders needed!")
            
    except Exception as e:
        logger.error(f"Error checking missing reports: {e}")


def post_thread_closed():
    global daily_thread_ts
    if SKIP_TODAY == "1":
        logger.info("SKIP_TODAY is set — skipping thread closed message.")
        return
    if not daily_thread_ts:
        logger.warning("No daily thread found for today. Skipping thread closed message.")
        return

    try:
        message = random.choice(THREAD_CLOSED_MESSAGES)
        app.client.chat_postMessage(
            channel=CHANNEL_ID,
            thread_ts=daily_thread_ts,
            text=message
        )
        logger.info("Posted thread closed message.")
    except Exception as e:
        logger.error(f"Error posting thread closed message: {e}")


def post_end_of_day_escalation():
    global daily_thread_ts
    if SKIP_TODAY == "1":
        logger.info("SKIP_TODAY is set — skipping end-of-day escalation.")
        return
    if not daily_thread_ts:
        logger.warning("No daily thread found for today. Skipping end-of-day escalation.")
        return

    try:
        missing_users = get_missing_users_today()
        if missing_users is None or not missing_users:
            return

        mentions = " ".join([f"<@{uid}>" for uid in missing_users])
        sad_gif = random.choice(END_OF_DAY_GIFS)
        text = (
            f"End of day check: still no update from {mentions}. "
            f"<@U068KKKNP9R>, this one needs attention.\n{sad_gif}"
        )

        app.client.chat_postMessage(
            channel=CHANNEL_ID,
            thread_ts=daily_thread_ts,
            text=text
        )
        logger.info(f"End-of-day escalation sent for missing users: {missing_users}")
    except Exception as e:
        logger.error(f"Error posting end-of-day escalation: {e}")

def _prev_workday(today: date) -> date:
    """Return the previous workday (skips weekends)."""
    delta = 3 if today.weekday() == 0 else 1  # Monday → Friday
    return today - timedelta(days=delta)


def _extract_today_section(raw_text: str) -> str:
    """Extract the 'Today' section from a standup post."""
    match = re.search(
        r'\*?Today[^:]*:\*?\s*(.+?)(?=\n\s*\*?(?:Yesterday|Blockers?|Risks?|Status)[^:]*:|$)',
        raw_text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return ""


def send_personal_standup_reminder():
    """DM the configured user with their 'Today' plan from yesterday's standup."""
    if not PERSONAL_REMINDER_USER_ID:
        return

    if not app or not supabase:
        logger.warning("send_personal_standup_reminder: app or supabase not ready")
        return

    today = date.today().isoformat()
    prev = _prev_workday(date.today()).isoformat()

    try:
        # Skip if user already posted today
        already = supabase.table("standup_reports").select("user_id").eq("user_id", PERSONAL_REMINDER_USER_ID).eq("date", today).execute()
        if already.data:
            logger.info("Personal reminder: user already posted today, skipping")
            return

        # Fetch previous workday's report
        result = supabase.table("standup_reports").select("raw_text").eq("user_id", PERSONAL_REMINDER_USER_ID).eq("date", prev).execute()
        if not result.data:
            logger.info(f"Personal reminder: no previous report found for {prev}")
            return

        raw_text = result.data[0]["raw_text"]
        today_section = _extract_today_section(raw_text)

        if today_section:
            body = f"*Yesterday you planned for today:*\n>{today_section}"
        else:
            body = f"_Could not parse your yesterday's plan — here's the full post:_\n>{raw_text[:300]}"

        thread_link = ""
        if daily_thread_ts:
            thread_link = f"\n\n<https://slack.com/archives/{CHANNEL_ID}/p{daily_thread_ts.replace('.', '')}|Open today's standup thread> — deadline is *13:00* 🕐"

        app.client.chat_postMessage(
            channel=PERSONAL_REMINDER_USER_ID,
            text=f"👋 Hey! Don't forget to post your standup before 13:00.\n\n{body}{thread_link}"
        )
        logger.info(f"Personal standup reminder sent to {PERSONAL_REMINDER_USER_ID}")

    except Exception as e:
        logger.error(f"Error sending personal standup reminder: {e}")


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
                    name="blue_heart",
                    timestamp=ts
                )

            except Exception as e:
                logger.error(f"Error saving report: {e}")

def send_deploy_notification():
    """Send a one-time deployment confirmation to the alert channel.
    Only fires when the DEPLOY_NOTIFY=1 env var is set, so restarts and
    crash-recoveries don't spam the channel.
    """
    if os.environ.get("DEPLOY_NOTIFY") != "1":
        return
    send_alert(
        "🚀 Bot deployed successfully!\n"
        "Current logic version: *Standup collection mode*."
    )
    logger.info("Deploy notification sent.")


def main():
    global app, supabase, daily_thread_ts
    
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        logger.error("SLACK_BOT_TOKEN or SLACK_APP_TOKEN not set")
        return
        
    app = App(token=SLACK_BOT_TOKEN)
    supabase = get_supabase_client()
    
    register_events(app)

    # Schedule jobs
    scheduler = BackgroundScheduler(timezone=LOCAL_TIMEZONE)
    # Weekday schedule in Europe/Paris local time.
    scheduler.add_job(post_daily_thread, 'cron', day_of_week='mon-fri', hour=9, minute=4)
    scheduler.add_job(send_personal_standup_reminder, 'cron', day_of_week='mon-fri', hour=9, minute=15)
    scheduler.add_job(check_missing_reports, 'cron', day_of_week='mon-fri', hour=12, minute=30)
    scheduler.add_job(post_thread_closed, 'cron', day_of_week='mon-fri', hour=18, minute=0)
    scheduler.add_job(post_end_of_day_escalation, 'cron', day_of_week='mon-fri', hour=21, minute=0)
    
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

    send_deploy_notification()

    # Start Slack Socket Mode
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    main()
