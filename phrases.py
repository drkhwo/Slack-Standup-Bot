# phrases.py
# Daily thread opening phrases used by post_daily_thread().

import random

# ─────────────────────────────────────────────
# DAILY THREAD OPENING PHRASES
# Used by post_daily_thread() to kick off the standup
# ─────────────────────────────────────────────

OPENING_PHRASES = [
    "Morning. Standup is open — keep it short, useful, and on the record.",
    "New day, same thread. What shipped, what is next, and what is in the way?",
    "Status window open. Facts first; side quests in subthreads.",
    "Standup is live. Drop the signal, skip the director's cut.",
    "Quick status check: done, next, blocked.",
    "The thread is live. Bring updates, not suspense.",
    "Morning sync starts here. If the plan changed, write it down.",
    "Standup is open. Keep it sharp and actionable.",
    "What shipped? What's next? What needs a hand?",
    "Daily status thread is live. Give us the useful version.",
    "No mystery, just status: yesterday, today, blockers.",
    "Status check-in is open. Concise is a feature.",
    "Thread unlocked. ETA changes and blockers belong here.",
    "Keep it factual, keep it moving, keep the blockers visible.",
    "13:00 is the deadline. The thread is the source of truth.",
    "One thread, three questions: yesterday, today, blockers.",
    "Standup is live. Keep the status here; move the debate to subthreads.",
    "Drop the update while it is still fresh.",
    "Monkey see, monkey do: make the status visible. 🐒",
    "Support your local monkey business: post the update before 13:00. 🐒",
    "Low battery, high signal. Drop the useful version.",
    "Case file open: what shipped, what is next, what is stuck?",
    "Ship check: what moved, what is next, what is stuck?",
    "Flow state starts with a clean status.",
    "Monkey business, minus the mystery.",
    "Need a quick win? Start with the status.",
]

def get_opening_phrase() -> str:
    """Return a random daily thread opener."""
    return random.choice(OPENING_PHRASES)
