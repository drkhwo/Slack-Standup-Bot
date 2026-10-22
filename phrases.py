# phrases.py
# Daily thread opening phrases used by post_daily_thread().

import random

# ─────────────────────────────────────────────
# DAILY THREAD OPENING PHRASES
# Used by post_daily_thread() to kick off the standup
# ─────────────────────────────────────────────

OPENING_PHRASES = [
    "Good morning, nephews and nieces. Pour the tea, then share: yesterday, today, blockers. 🍵",
    "The kettle is warm and the thread is open. Come, sit, tell your uncle how the work goes.",
    "A good update is like good tea: not too long, not too weak.",
    "Morning. Before the day begins, let us look at where we have been and where we are going.",
    "Sharing your status is not a chore. It is how a team remembers itself.",
    "The thread is open. Bring your progress, your plans, and the stones in your path.",
    "Even the mightiest river starts as a few drops. Small updates count too.",
    "Tea is ready. So is the thread. Only one of them will wait for you until 13:00.",
    "There is no shame in a stuck task, only in a silent one. If something is blocked, say so here.",
    "Good morning. Life happens wherever you are — and standup happens right here.",
    "A blocker shared before noon is half a blocker by lunch.",
    "Ah, a new day. Let us begin it the civilized way: with tea and a status update.",
    "Do not rush the leaves, but do not forget the cup. Update before 13:00.",
    "It is time to look inward — and then type outward. What moved, what is next, what is stuck?",
    "Sometimes the best way to solve a problem is to tell your teammates about it.",
    "The morning is quiet, the tea is jasmine, the thread is open.",
    "Good morning, my friends. Hope is something you give yourself — a clear plan for today helps too.",
    "A plan written down is a plan half done. Share yours here.",
    "Open the thread, open the mind. Short and honest is the best flavor.",
    "You must never give up when your ticket is hard. But you may ask for help here.",
    "The tea is hot. The thread is open. Your uncle is listening.",
    "Even a lost traveler can find the way if someone points. Name your blockers.",
    "New day, fresh leaves. What did yesterday brew, and what will today?",
    "Welcome back to the tea shop. Today's specials: yesterday, today, blockers.",
]

def get_opening_phrase() -> str:
    """Return a random daily thread opener."""
    return random.choice(OPENING_PHRASES)
