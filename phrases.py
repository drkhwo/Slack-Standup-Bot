# phrases.py
# All bot copy: daily thread openers + Michael Scott quotes + motivational boosts

import random

# ─────────────────────────────────────────────
# DAILY THREAD OPENING PHRASES
# Used by post_daily_thread() to kick off the standup
# ─────────────────────────────────────────────

OPENING_PHRASES = [
    # Classic energy
    "Alright team, let's hear it. What's the plan? 🗓️",
    "Another day, another diff. Drop your updates! 💻",
    "Good morning, humans. Status report. 🤖",
    "The standup is now open. Your keyboard is the mic. 🎤",
    "Clocking in. What are we building today? 🔨",

    # Slightly chaotic
    "Rise and grind (or just rise, no pressure). Standup time! ☀️",
    "Bugs fear you. Ship it. Now talk about it. 🐛",
    "Today's agenda: fix things, break nothing, report here. 🧯",
    "It's standup o'clock. Set your blockers free. 🕐",
    "Hello and welcome to your daily 'what did I actually do' session. 📋",

    # Movie/pop culture vibes
    "This is the way. (To post your standup.) 🪖",
    "Winter is coming. But first: standup. ❄️",
    "You shall not pass... without posting your update. 🧙",
    "To infinity and beyond — but first, blockers? 🚀",
    "I am inevitable. (So is this standup.) ⚙️",

    # Wholesome
    "Good morning! Hope your coffee is strong and your bugs are few. ☕",
    "New day, fresh start. Let's make it count. ✨",
    "Team check-in time! What's cooking? 👨‍🍳",
    "You're all doing great. Now tell me how great. 💪",
    "Proud of this team every day. Now — what's up? 🙌",

    # Start / end of week
    "It's Monday. We survived the weekend. Standup! 💀",
    "Week 1, Day 1 energy. Let's go. 🏁",
    "Last standup of the week. Make it legendary. 🏆",
    "One more day. You got this. 🎉",

    # Nerdy
    "Initializing daily sync protocol... done. Awaiting input. 🖥️",
    "git status: team — please respond. 📡",
    "sudo post_standup --today --no-skip 🐧",
    "Stack trace of your day starts here. 📊",
    "404: standup not found. Please submit yours. 🔍",
]


# ─────────────────────────────────────────────
# MICHAEL SCOTT MOTIVATIONAL QUOTES
# Sent randomly up to 3x per day in the standup thread
# Positive, recognizable, non-offensive
# ─────────────────────────────────────────────

MICHAEL_SCOTT_QUOTES = [
    "\"You miss 100% of the shots you don't take. – Wayne Gretzky\" – Michael Scott 🏒",
    "Would I rather be feared or loved? Easy. Both. I want people to be afraid of how much they love this team. ❤️",
    "I am Beyoncé, always. And so are you right now. 👑",
    "Sometimes I'll start a sentence and I don't even know where it's going. I just hope I find it along the way. Keep building! 🛤️",
    "I am a great boss. I can say that because several people have said it to me, and I am one of them. Today YOU are the great one. 🏆",
    "Do I need to be liked? Absolutely not. Do I need to be productive? Yes. And that's you today. 💪",
    "The people I work with are like family — annoying sometimes, but love them anyway. You are loved. 💛",
    "What is the most important thing for a company? Is it the equipment? The people? Wrong — it's the people shipping things. Go! 🚢",
    "I have cause. And I will not rest until I have gotten the daily standup update. 🫡",
    "There's no such thing as too much fun. There IS such a thing as too few status updates. Drop yours! 📝",
    "An office is not for dying. An office is a place to live life to the fullest. Deliver value, laugh, commit. 🌟",
    "I'm not superstitious, but I am a little stitious. I DO believe today will be amazing. 🔮",
    "I took this job because I thought it would be fun. And it IS fun — because of people like you. Let's go! 🎉",
    "It's a beautiful day. The sun is shining. And I'm about to see your standup update. Life is good. ☀️",
    "I love this team so much sometimes I cry. In a good way. Like right now reading your update. 😭💛",
]


# ─────────────────────────────────────────────
# GIF URLS (Giphy direct links)
# ─────────────────────────────────────────────

OPENING_GIFS = [
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    "https://media.giphy.com/media/3o7btNa0RUYa5E7iiQ/giphy.gif",
    "https://media.giphy.com/media/CjmvTCZf2U3p09Cn0h/giphy.gif",
    "https://media.giphy.com/media/13HgwGsXF0aiGY/giphy.gif",
    "https://media.giphy.com/media/xT9IgG50Lg7rusRgqA/giphy.gif",
    "https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif",
    "https://media.giphy.com/media/l3q2K5jinAlChoCLS/giphy.gif",
    "https://media.giphy.com/media/d3mlE7uhX8KFgEmY/giphy.gif",
]

MOTIVATIONAL_GIFS = [
    "https://media.giphy.com/media/5GoVLqeAOo6PK/giphy.gif",
    "https://media.giphy.com/media/XRB1uf2F9bGOA/giphy.gif",
    "https://media.giphy.com/media/3ohzdIuqJoo8QdKlnW/giphy.gif",
    "https://media.giphy.com/media/26tOZ42Mg6pbTUPHW/giphy.gif",
    "https://media.giphy.com/media/1gdie9fKPGxZWGgTw6/giphy.gif",
    "https://media.giphy.com/media/a0h7sAqON67nO/giphy.gif",
    "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif",
    "https://media.giphy.com/media/nV92wySC3iMGhAmR71/giphy.gif",
]


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def get_opening_phrase(include_gif: bool = False) -> str:
    """Return a random daily thread opener, optionally with a GIF."""
    phrase = random.choice(OPENING_PHRASES)
    if include_gif:
        gif = random.choice(OPENING_GIFS)
        return f"{phrase}\n{gif}"
    return phrase


def get_michael_quote(include_gif: bool = True) -> str:
    """Return a random Michael Scott motivational quote, optionally with a GIF."""
    quote = random.choice(MICHAEL_SCOTT_QUOTES)
    if include_gif:
        gif = random.choice(MOTIVATIONAL_GIFS)
        return f"{quote}\n{gif}"
    return quote


def should_send_boost(boost_count_today: int, max_boosts: int = 3) -> bool:
    """
    Decide whether to send a motivational boost after this standup reply.
    Hard cap at max_boosts per day; ~28% chance per reply below the cap.
    Calibrated for teams of 10-20 people to hit ~3 boosts/day naturally.
    """
    if boost_count_today >= max_boosts:
        return False
    return random.random() < 0.28
