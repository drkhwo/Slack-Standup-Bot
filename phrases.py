# phrases.py
# Daily thread opening phrases used by post_daily_thread().

import random

# ─────────────────────────────────────────────
# DAILY THREAD OPENING PHRASES
# Used by post_daily_thread() to kick off the standup
# ─────────────────────────────────────────────

OPENING_PHRASES = [
    "Good morning, nephews and nieces. Pour the tea, then share: yesterday, today, blockers.",
    "The kettle is warm. Come, sit, and tell your uncle how the work goes.",
    "The first update of the day gets the good jasmine.",
    "Bring your plans, and bring the stones in your path. Someone here has probably moved that stone before.",
    "No epic poems, please. Three honest lines will do.",
    "Tea is ready. So is the thread. Only one of them will wait for you until 13:00.",
    "Stuck on something? Say so this morning, while there is still a whole day to fix it.",
    "Ah, a new day. Let us begin it the civilized way: with tea and a status update.",
    "Good tea takes time. A good update takes about two minutes.",
    "It is time to look inward and ask yourself the big questions. Mainly: what did I do yesterday?",
    "Sometimes the best way to solve a problem is to tell your teammates about it.",
    "Jasmine tea this morning, so your uncle is in a very good mood. Now is the time to mention blockers.",
    "There is nothing wrong with letting the people who love you help you. Your teammates count, mostly.",
    "Welcome back to the tea shop. Today's specials: yesterday, today, blockers.",
    "Your uncle slept through most of yesterday. What did he miss?",
    "If yesterday went badly, write that too. Your uncle has had worse days, some of them in prison.",
    "Yesterday's Today is today's Yesterday. Your uncle finds this very funny.",
    "Post before 13:00 and your uncle will not have to come find you with a teapot.",
    "Prince Zuko never wrote a standup, and look how his year went.",
]

def get_opening_phrase() -> str:
    """Return a random daily thread opener."""
    return random.choice(OPENING_PHRASES)
