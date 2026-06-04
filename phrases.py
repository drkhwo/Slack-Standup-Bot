# phrases.py
# Daily thread opening phrases used by post_daily_thread().

import random

# ─────────────────────────────────────────────
# DAILY THREAD OPENING PHRASES
# Used by post_daily_thread() to kick off the standup
# ─────────────────────────────────────────────

OPENING_PHRASES = [
    "Good morning. The standup thread is live. Bring the signal. ☀️",
    "Daily check-in is open. Yesterday, today, blockers. Keep it crisp. 🧵",
    "Status window is open. What changed, what ships, what is stuck? 📍",
    "New day, same thread discipline. Drop the update before 13:00. ⏰",
    "Standup is open. Small updates beat mystery progress. 🔎",
    "Morning sync starts here. Clear status, clear blockers, clear next step. 🛠️",
    "Thread is up. Ship notes, ETA changes, and risks go here. 📦",
    "Daily roll call. What landed, what moves today, what needs help? 🎯",
    "The board does not update itself. Statuses in thread, please. 📋",
    "Check-in time. If something slipped, name the new ETA. 🧭",
    "Standup is live. Less suspense, more status. ⚡",
    "Morning thread is ready. Post the useful bits and keep moving. ☕",
    "Daily status drop is open. Make future-you easy to understand. 📝",
    "The 13:00 deadline is closer than it looks. Updates go here. 🕐",
    "Standup mode: on. Blockers, progress, and today's finish line. 🚦",
    "Team pulse check. What is done, what is next, what is at risk? 📡",
    "Status thread unlocked. Add facts, ETAs, and blockers. 🔓",
    "Good morning. Let the thread know what reality looks like today. 🌤️",
    "Daily coordination starts here. Short, concrete, actionable. 🧩",
    "Standup is open. If it changed the plan, it belongs in the update. 🧠",
]

def get_opening_phrase() -> str:
    """Return a random daily thread opener."""
    return random.choice(OPENING_PHRASES)
