# phrases.py
# Daily thread opening phrases used by post_daily_thread().

import random

# ─────────────────────────────────────────────
# DAILY THREAD OPENING PHRASES
# Used by post_daily_thread() to kick off the standup
# ─────────────────────────────────────────────

OPENING_PHRASES = [
    "Good morning, team. Daily standup is open. ☀️",
    "Status thread is live. Drop your updates here. 🧵",
    "New day, new progress. Let's hear the plan. 🚀",
    "Standup time. What moved yesterday, and what ships today? 📦",
    "Morning check-in is open. Share your status and blockers. 🛠️",
    "Daily thread is ready. Post your update before the deadline. ⏰",
    "Another workday, another standup. What is the focus today? 🎯",
    "Roll call for builders: yesterday, today, blockers. 💻",
    "Team sync starts here. Keep it short, clear, and actionable. 📋",
    "Keyboard ready, coffee ready, standup ready. Let's go. ☕",
    "Progress report time. What shipped, what is next, what is blocked? 📡",
    "Daily status window is open. Share the signal, skip the noise. 🔍",
    "Standup thread is up. Post the essentials and keep moving. ⚡",
    "Let's get the board moving. Updates in thread, discussions in subthreads. 🧠",
    "Good morning. What did you finish, what are you tackling, what needs help? 🧭",
    "Thread is open. Share wins, today's target, and any risks. 🏁",
    "Check-in time. What is done, what is next, and where are you stuck? 🧱",
    "Daily sync protocol initialized. Awaiting team input. 🤖",
    "Standup is live. Clear updates first, deep dives second. 🎤",
    "Another day to ship. Post your status and keep the momentum up. 🔨",
]

def get_opening_phrase() -> str:
    """Return a random daily thread opener."""
    return random.choice(OPENING_PHRASES)
