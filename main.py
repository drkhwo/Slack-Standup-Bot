import os
import json
import logging
import re
from datetime import date, timedelta
import random
from pathlib import Path
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

# Slack users whose accounts are deactivated but whose identity records may
# still appear in stale roster data. Keep this list in sync when accounts are
# reactivated or deactivated.
DEACTIVATED_USER_IDS = frozenset({
    "U097GKF641M",  # Cristian Matzov
    "U08MW9K5K0U",  # Ban Markovic
    "U097GKK3UUX",  # Georgi Todorov
    "U09T69U1Y5V",  # Sebastian
    "U088WHYP2P6",  # Gvantsa Nebadze
    "U0B8285T563",  # matei
})

# Mapping: Slack User ID -> Vacation Tracker user identity.
# Vacation Tracker user IDs are the primary matching key; email/name are fallbacks.
TEAM_MAPPING = {
    # == @eng-team ==
    "U02H9RXPKGT": {"vt_user_id": "slack-422616fd-66dc-47a2-81dc-f032f05c1c4d", "name": "Alexey Leshchuk", "email": "a.leshchuk@replika.ai"},
    "U08SKHD45U2": {"vt_user_id": "slack-8596b09c-455c-45d3-a169-f780cb4a2bb4", "name": "Anastasia Kondratyuk", "email": "nastassia@replika.com"},
    "U06A6MV64R2": {"vt_user_id": "slack-cd6e696b-b46c-4016-a83b-6f33bdec289d", "name": "andrei", "email": "a.vorsin@replika.ai"},
    "U035U3KTFL5": {"vt_user_id": "slack-e8a42dfa-6dc0-421a-ae5d-977b46ec1cdb", "name": "Anton Tyutin", "email": "tapoton@replika.ai"},
    "U085J8B5TJ6": {"vt_user_id": "slack-c847534e-34c8-49eb-b711-5a7df4efa0bd", "name": "eddy", "email": "ed@replika.ai"},
    "U011Q8J1PDK": {"vt_user_id": "slack-9c1dd668-ff38-4e5f-b055-094d54eb4178", "name": "Georgii Andrianov", "email": "g.andrianov@replika.ai"},
    "U09QE0E0HHQ": {"vt_user_id": "slack-986ddb5f-8fca-4fba-bb75-94c26a22afb7", "name": "Giorgio", "email": "giorgio@replika.com"},
    "U09RAPHVDPG": {"vt_user_id": "", "name": "Gena", "email": "henadz@replika.com"},
    "U0965UA3XQ8": {"vt_user_id": "slack-8878392a-0160-4ed5-859b-b38e2b76aeb8", "name": "maksim", "email": "maksim@replika.com"},
    "U08EFQCMJ3U": {"vt_user_id": "slack-720b8eaa-3d39-4bcd-9d96-57081203ab2d", "name": "Paweł", "email": "pawel@replika.com"},
    "USMQ8CRU6": {"vt_user_id": "slack-a99afe34-239c-4d72-b80a-40ee405b8e5f", "name": "Semyon Vlasov", "email": "semyon@replika.ai"},
    "U04SBH53P9C": {"vt_user_id": "slack-16602c14-6349-4187-8d72-f29c97ad74ac", "name": "Sergei Mironov", "email": "s.mironov@replika.ai"},
    "U0821BRMJ4R": {"vt_user_id": "slack-876c64e7-4bae-496c-a5b8-2bdfbc192440", "name": "Stan Khvo", "email": "stas@replika.ai"},
    "U098DPA85PY": {"vt_user_id": "slack-3d7c669c-4433-4bad-8a85-76c86e71caa6", "name": "Wojciech Klarowski", "email": "wojciech@replika.com"},
    "U09MF4SB7C2": {"vt_user_id": "slack-f6986bc1-2c20-46ba-b9a1-dcef0329346c", "name": "John Deda", "email": "johndeda@replika.com"},
    
    # == @brand-team ==
    "U07SR89J8NA": {"vt_user_id": "slack-9df7fc6d-ecb9-4c8d-bb8f-779e39a91a84", "name": "artiom", "email": "artiom@replika.com"},
    "U0B670M7HU6": {"vt_user_id": "", "name": "danil levinson", "email": ""},
    "U0B6RSB4M5E": {"vt_user_id": "slack-4c5703ea-8892-429c-94ff-4d1f09fb7ab3", "name": "Vladimir Lesunov", "email": "vlad@replika.com"},

    # == @gtm-team ==
    "U0BMCE4HM7D": {"vt_user_id": "", "name": "Arman", "email": "arman@replika.com"},
    "U0BQ926P1B4": {"vt_user_id": "", "name": "Vadym Netrebko", "email": "vadym@replika.com"},
    
    # == Others ==
    "U068KKKNP9R": {"vt_user_id": "slack-893f60ed-5bb0-429c-b03b-68e0eb54c35a", "name": "dmytro klochko", "email": "1@replika.com"}
}

def _build_team_user_ids():
    """Build the active standup roster from the identity map and exclusions."""
    return [
        uid
        for uid in TEAM_MAPPING
        if uid != "U068KKKNP9R" and uid not in DEACTIVATED_USER_IDS
    ]


# Collect active user IDs for report tracking, excluding CEO and deactivated users.
TEAM_USER_IDS = _build_team_user_ids()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REACTION_ALIASES = (
    "flow-state",
    "monkey-business",
    "investigating",
    "tired-monke",
    "together-4",
    "enough-for-today",
    "stop-nerding",
    "ship-smth",
    "mvp",
    "mvp-2",
    "together-3",
    "together-5",
    "pink-monke",
    "monkey-zen",
    "omg-monkey",
    "matrix-code",
    "matrix-monitors",
)

MEDIA_MANIFEST_PATH = Path(__file__).resolve().parent / "assets" / "monkey-business" / "manifest.json"
with MEDIA_MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
    MEDIA_MANIFEST = json.load(manifest_file)
MEDIA_ALIASES = tuple(MEDIA_MANIFEST)

REMINDER_MESSAGES = (
    "Hey {MENTIONS} — your standup update is still missing. Reply in this thread with Yesterday, Today, and Blockers/Risks before 13:00.",
    "Hey {MENTIONS} — quick nudge: the thread is still waiting on Yesterday, Today, and Blockers/Risks. Please post before 13:00.",
    "Hey {MENTIONS} — no update from you yet. Add Yesterday, Today, and Blockers/Risks here before 13:00.",
    "Hey {MENTIONS} — the thread is missing your update. Keep it brief: Yesterday, Today, Blockers/Risks. Deadline: 13:00.",
    "Hey {MENTIONS} — make the status visible. Reply here with Yesterday, Today, and Blockers/Risks before 13:00. 🐒",
    "Hey {MENTIONS} — support your local monkey business and drop your update here before 13:00: Yesterday, Today, and Blockers/Risks.",
)

THREAD_CLOSED_MESSAGE = "DDL passed. Thread closed."


def _get_media_path(alias):
    """Resolve an approved media alias through the checked-in manifest."""
    if alias not in MEDIA_ALIASES:
        raise ValueError(f"Unsupported media alias: {alias}")

    entry = MEDIA_MANIFEST[alias]
    media_path = Path(__file__).resolve().parent / entry["path"]
    if media_path.suffix.lower() not in {".gif", ".png"}:
        raise ValueError(f"Unsupported runtime media type: {media_path}")
    if not media_path.is_file():
        raise FileNotFoundError(f"Media asset does not exist: {media_path}")
    return media_path


def _upload_thread_media_or_text(text, media_alias):
    """Upload local thread media, falling back to the same thread as text."""
    try:
        app.client.files_upload_v2(
            channel=CHANNEL_ID,
            thread_ts=daily_thread_ts,
            file=str(_get_media_path(media_alias)),
            initial_comment=text,
        )
        return True
    except Exception as upload_error:
        logger.warning(f"Could not upload thread media; using text fallback: {upload_error}")
        try:
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text=text,
            )
        except Exception as fallback_error:
            logger.error(f"Could not post text fallback: {fallback_error}")
        return False

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize clients
app = None
supabase = None

VACATION_TRACKER_API_URL = "https://api.vacationtracker.io"


def _normalize_vacation_tracker_value(value):
    return (value or "").strip().casefold()


def _build_vacation_tracker_lookup():
    vt_user_id_to_uid = {}
    email_to_uid = {}
    name_to_uid = {}

    for uid in _build_team_user_ids():
        identity = TEAM_MAPPING[uid]
        if isinstance(identity, str):
            vt_user_id = ""
            name = identity
            email = ""
        else:
            vt_user_id = identity.get("vt_user_id", "")
            name = identity.get("name", "")
            email = identity.get("email", "")

        normalized_vt_user_id = _normalize_vacation_tracker_value(vt_user_id)
        normalized_email = _normalize_vacation_tracker_value(email)
        normalized_name = _normalize_vacation_tracker_value(name)

        if normalized_vt_user_id:
            vt_user_id_to_uid[normalized_vt_user_id] = uid
        if normalized_email:
            email_to_uid[normalized_email] = uid
        if normalized_name:
            name_to_uid[normalized_name] = uid

    return vt_user_id_to_uid, email_to_uid, name_to_uid


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

    vt_user_id_to_uid, email_to_uid, name_to_uid = _build_vacation_tracker_lookup()

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
                user_vt_id = _normalize_vacation_tracker_value(user_info.get("id") or leave.get("userId"))
                user_email = _normalize_vacation_tracker_value(user_info.get("email"))
                user_name = _normalize_vacation_tracker_value(user_info.get("name"))
                slack_user_id = (
                    vt_user_id_to_uid.get(user_vt_id)
                    or email_to_uid.get(user_email)
                    or name_to_uid.get(user_name)
                )

                if slack_user_id:
                    vacation_users.add(slack_user_id)
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


def get_thread_reported_users():
    """Return team members who have any non-bot reply in the active Slack thread."""
    if not app or not CHANNEL_ID or not daily_thread_ts:
        return set()

    reported_users = set()
    cursor = None

    try:
        while True:
            request = {
                "channel": CHANNEL_ID,
                "ts": daily_thread_ts,
                "limit": 1000,
            }
            if cursor:
                request["cursor"] = cursor

            response = app.client.conversations_replies(**request)

            messages = response.get("messages") or []
            if not isinstance(messages, list):
                messages = []

            for message in messages:
                user_id = message.get("user")
                if not user_id or message.get("bot_id"):
                    continue
                if message.get("subtype") in {"bot_message", "message_deleted"}:
                    continue
                if user_id in TEAM_USER_IDS:
                    reported_users.add(user_id)

            metadata = response.get("response_metadata") or {}
            next_cursor = metadata.get("next_cursor") if isinstance(metadata, dict) else ""
            cursor = next_cursor if isinstance(next_cursor, str) and next_cursor else None
            if not cursor:
                break

        if reported_users:
            logger.info(f"Users found in Slack thread history: {reported_users}")
        return reported_users
    except Exception as e:
        logger.warning(f"Could not reconcile Slack thread history: {e}")
        return set()


def get_missing_users_today():
    """Return users who still have not posted an update today."""
    if not supabase:
        logger.error("Supabase client not initialized")
        return None

    today = date.today().isoformat()

    response = supabase.table("standup_reports").select("user_id").eq("date", today).execute()
    reported_users = {row["user_id"] for row in response.data}
    reported_users.update(get_thread_reported_users())

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
        standup_text = (
            f"{phrase} <!subteam^S074DP77Q9H> <!subteam^S08EJBE5Q4X> <!subteam^S0BHNJ7J12M> 🍌\n\n"
            "*Daily status thread*\n"
            "*Reply in the active thread before 13:00 with:*\n"
            "*Yesterday:* what shipped or merged. If this continues yesterday's work, quote your previous update and add the current status.\n"
            "*Today:* what you will complete today and, if relevant, how many days remain.\n"
            "*Blockers / Risks:* who or what you need to unblock you.\n"
            "*Keep status in this thread; move discussions to subthreads.*\n"
            "*If something will not be finished today, state the remaining time.*\n\n"
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
        send_alert(f"Today's standup thread is live: <{thread_link}|open the active thread>")
        
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
                text="⚠️ _Vacation Tracker is unavailable, so today's leave status is unknown. Monkey Business continues, but we will not guess who is out._"
            )
        elif vacations:
            mentions = ", ".join([f"<@{uid}>" for uid in vacations])
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text=f"🌴 *Out today — confirmed by Vacation Tracker:* {mentions}\nEnjoy the PTO. We'll keep the status thread moving."
            )
        else:
            app.client.chat_postMessage(
                channel=CHANNEL_ID,
                thread_ts=daily_thread_ts,
                text="*Full team today:* Vacation Tracker reports no absences. Let's keep the status moving."
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
        
        if missing_users:
            mentions = " ".join([f"<@{uid}>" for uid in missing_users])
            message = random.choice(REMINDER_MESSAGES).replace("{MENTIONS}", mentions)
            _upload_thread_media_or_text(message, random.choice(MEDIA_ALIASES))
            logger.info(f"Reminded missing users: {missing_users}")
            send_alert(f"Standup reminder sent to {len(missing_users)} missing reporter(s).")
        else:
            logger.info("All active users have reported. No reminders needed!")
            send_alert("All standup reports are in. The status thread is complete.")
            
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
        message = THREAD_CLOSED_MESSAGE
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
        text = (
            f"End-of-day check: {mentions} still have no update in the active thread. "
            f"<@U068KKKNP9R>, please take a look."
        )

        _upload_thread_media_or_text(text, random.choice(MEDIA_ALIASES))
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
            text = (
                "Quick nudge: your standup update is still missing. Please reply in today's active thread before 13:00.\n\n"
                f"*Yesterday's plan for Today:*\n>{today_section}"
            )
        else:
            text = (
                "Quick nudge: your standup update is still missing. I couldn't isolate yesterday's Today section, so here's the full previous post. "
                "Please reply in today's active thread before 13:00.\n\n"
                f"*Full previous post:*\n>{raw_text[:300]}"
            )

        if daily_thread_ts:
            text += f"\n\n<https://slack.com/archives/{CHANNEL_ID}/p{daily_thread_ts.replace('.', '')}|Open today's active standup thread> — deadline is *13:00*"

        app.client.chat_postMessage(
            channel=PERSONAL_REMINDER_USER_ID,
            text=text,
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
                
                reaction_name = random.choice(REACTION_ALIASES)
                app_instance.client.reactions_add(
                    channel=CHANNEL_ID,
                    name=reaction_name,
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
        "🚀 Standup bot is back online.\n"
        "Mode: *Standup collection*."
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
    scheduler.add_job(post_thread_closed, 'cron', day_of_week='mon-fri', hour=13, minute=1)
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
