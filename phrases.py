# phrases.py
# Daily thread opening phrases used by post_daily_thread().

import random

# ─────────────────────────────────────────────
# DAILY THREAD OPENING PHRASES
# Used by post_daily_thread() to kick off the standup
# ─────────────────────────────────────────────

OPENING_PHRASES = [
    "Good morning. Regional Management has opened the branch status ceremony. ☀️",
    "Daily check-in is live. Yesterday, today, blockers. Make the clipboard proud. 🧵",
    "Status window is open. What changed, what ships, what is causing conference-room tension? 📍",
    "New day, same beautiful paper trail. Drop the update before 13:00. ⏰",
    "Standup is open. Mystery progress is not an approved department strategy. 🔎",
    "Morning sync starts here. Progress, blockers, ETAs, and absolutely no plot twists. 🛠️",
    "Thread is up. Ship notes, ETA changes, risks, and tiny miracles go here. 📦",
    "Daily roll call. What landed, what moves today, what needs a managerial stare? 🎯",
    "The board does not update itself. Regional Management checked. 📋",
    "Check-in time. If something slipped, name the new ETA with branch-manager confidence. 🧭",
    "Standup is live. Less suspense, more status, maximum paperwork energy. ⚡",
    "Morning thread is ready. Post the useful bits before the imaginary staff meeting starts. ☕",
    "Daily status drop is open. Make future-you and the audit trail proud. 📝",
    "The 13:00 deadline is closer than it looks. The clock is doing management. 🕐",
    "Standup mode: on. Blockers, progress, and today's finish line enter the chat. 🚦",
    "Team pulse check. What is done, what is next, what deserves a dramatic pause? 📡",
    "Status thread unlocked. Add facts, ETAs, blockers, and just enough accountability. 🔓",
    "Good morning. Let the thread know what reality looks like before reality improvises. 🌤️",
    "Daily coordination starts here. Short, concrete, and worthy of a laminated memo. 🧩",
    "Standup is open. If it changed the plan, Regional Management wants it in writing. 🧠",
]

def get_opening_phrase() -> str:
    """Return a random daily thread opener."""
    return random.choice(OPENING_PHRASES)
