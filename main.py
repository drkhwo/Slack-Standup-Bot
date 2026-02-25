import os
import logging
from datetime import date, datetime
import random
import time

# Third-party imports
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

# Global state to track the daily thread timestamp
daily_thread_ts = None

# Hardcoded team list for MVP (Replace with real IDs)
TEAM_USER_IDS = ["U12345678", "U87654321"] 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize clients
# Defer app initialization to main or try block to avoid immediate crash on import if tokens missing
app = None
supabase = None

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
        # Persist ts so bot survives restarts
        if supabase:
            try:
                supabase.table("bot_state").upsert({"key": "daily_thread_ts", "value": daily_thread_ts}).execute()
            except Exception as e:
                logger.warning(f"Could not save bot state: {e}")
        
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
        # Fetch reports for today from Supabase
        response = supabase.table("standup_reports").select("user_id").eq("date", today).execute()
        reported_users = {row["user_id"] for row in response.data}
        
        missing_users = [uid for uid in TEAM_USER_IDS if uid not in reported_users]
        
        if missing_users:
            mentions = " ".join([f"<@{uid}>" for uid in missing_users])
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text=f"Hey {mentions}, waiting for your update! ⏳"
            )
            logger.info(f"Reminded users: {missing_users}")
        else:
            logger.info("All users have reported!")
            
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
                # 1. Ищем, есть ли уже отчет от этого юзера за сегодня
                existing_record = supabase.table("standup_reports").select("raw_text").eq("user_id", user_id).eq("date", today).execute()
                
                if existing_record.data:
                    # Если отчет уже есть, склеиваем старый текст с новым
                    old_text = existing_record.data[0]["raw_text"]
                    final_text = f"{old_text}\n\n[Addition:]:\n{text}"
                    
                    # Обновляем существующую запись
                    supabase.table("standup_reports").update({"raw_text": final_text}).eq("user_id", user_id).eq("date", today).execute()
                    logger.info(f"Updated existing report for {user_id}")
                else:
                    # Если отчета еще нет, создаем новую запись
                    data = {
                        "user_id": user_id,
                        "date": today,
                        "raw_text": text,
                        "thread_ts": ts
                    }
                    supabase.table("standup_reports").insert(data).execute()
                    logger.info(f"Inserted new report for {user_id}")
                
                # Ставим галочку на сообщение в Slack
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

    # -------- СТРОЧКА ДЛЯ ТЕСТА --------
    post_daily_thread()
    # -----------------------------------

    # Start Slack Socket Mode
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    main()