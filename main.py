import os
import logging
import re
import json
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

# Маппинг: Slack User ID -> Имя, как оно пишется в Vacation Tracker
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

# Бот сам соберет все ключи (ID) в список для проверок должников
# Исключаем ID CEO (@dk - U068KKKNP9R)
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

def get_vacation_users():
    vacation_users = set()
    if not app:
        return "error"
    try:
        yesterday_ts = time.time() - 24 * 3600
        history = app.client.conversations_history(
            channel="CJS19HLG1",  # Твой канал #vacations
            oldest=str(yesterday_ts)
        )
        for msg in history.get("messages", []):
            if msg.get("bot_id") or msg.get("app_id"):
                # Трюк: превращаем всё сообщение (включая скрытые блоки) в строку
                full_msg_text = json.dumps(msg, ensure_ascii=False).lower()
                
                for uid, name in TEAM_MAPPING.items():
                    if name.lower() in full_msg_text:
                        vacation_users.add(uid)
        logger.info(f"Users on vacation today: {vacation_users}")
        return vacation_users
    except Exception as e:
        logger.error(f"Error fetching vacations channel history: {e}")
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
        
        # Сохраняем ts в базу
        if supabase:
            try:
                supabase.table("bot_state").upsert({"key": "daily_thread_ts", "value": daily_thread_ts}).execute()
            except Exception as e:
                logger.warning(f"Could not save bot state: {e}")
        
        # ОТДЕЛЬНЫЙ ПОСТ ПРО ОТПУСКНИКОВ СРАЗУ ПОСЛЕ ТРЕДА
        vacations = get_vacation_users()
        
        if vacations == "error":
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text="⚠️ _Не удалось проверить отпуска (ошибка доступа к каналу или API)._"
            )
        elif vacations:  # Если отпускники нашлись
            mentions = ", ".join([f"<@{uid}>" for uid in vacations])
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text=f"🌴 *Сегодня отсутствуют (Vacation/Off):* {mentions}\n_Хорошего отдыха!_"
            )
        else:  # Если множество пустое
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text="🌴 *Сегодня все в строю!* (Отпускников не найдено)"
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
        # 1. Получаем тех, кто УЖЕ отписался
        response = supabase.table("standup_reports").select("user_id").eq("date", today).execute()
        reported_users = {row["user_id"] for row in response.data}
        
        # 2. Получаем отпускников через нашу новую функцию
        vacation_users = get_vacation_users()
        if vacation_users == "error":
            vacation_users = set()  # Если ошибка, считаем, что отпускников нет, чтобы не сломать код

        # 3. Вычисляем должников (берем TEAM_USER_IDS, где уже нет CEO)
        missing_users = [
            uid for uid in TEAM_USER_IDS 
            if uid not in reported_users and uid not in vacation_users
        ]
        
        # 4. Мемный пинг
        if missing_users:
            MEMES = [
                "I am once again asking for your daily updates... 🧤",
                "Error 404: Standup reports not found. 🤖",
                "Where is the standup, Lebowski?! 🎳",
                "Git push origin standup_report — waiting for your statuses! 🐙",
                "The 12:00 sync is approaching fast! Drop your updates! ⏳",
                "Houston, we have a problem. Не вижу ваших отчетов! 🚀"
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

    # -------- СТРОЧКИ ДЛЯ ТЕСТА --------
    post_daily_thread()
    check_missing_reports()
    # -----------------------------------

    # Start Slack Socket Mode
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()

if __name__ == "__main__":
    main()