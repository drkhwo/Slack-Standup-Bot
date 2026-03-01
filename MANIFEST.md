# Slack Standup Bot — Genesis Manifest

**Version:** 0.1.0 (Genesis)
**Date:** 2025-02-25
**Author:** stas@replika.ai

---

## What is this?

Slack Standup Bot — бот для автоматизации ежедневных стендапов в Slack. Создаёт тред каждое утро, собирает отчёты команды, сохраняет их в базу и напоминает тем, кто забыл отписаться.

---

## Architecture

```
┌──────────────┐     Socket Mode      ┌──────────────┐
│  Slack API   │◄────────────────────►│  Python Bot  │
│  (Channels)  │                      │  (main.py)   │
└──────────────┘                      └──────┬───────┘
                                             │
                                      ┌──────▼───────┐
                                      │   Supabase   │
                                      │  (Postgres)  │
                                      └──────────────┘
```

**Tech stack:** Python 3.10+ · Slack Bolt · Supabase · APScheduler · Socket Mode

---

## Features (v0.1.0)

### Daily Thread Posting
- Автоматический пост в канал каждый день в 09:00
- Рандомная открывающая фраза из пула (phrases.py)
- Структурированный шаблон: Yesterday / Today / Blockers
- Сохранение `thread_ts` в Supabase для выживания после рестартов

### Report Collection
- Слушает сообщения в standup-треде через Socket Mode
- Фильтрует сообщения ботов (bot_id)
- Фильтрует сообщения из других тредов
- Сохраняет отчёт в `standup_reports`: user_id, date, raw_text, thread_ts
- Ставит ✅ реакцию на подтверждённые сообщения

### Missing Report Reminders
- Проверка в 11:30 — кто ещё не отписался
- Пинг пользователей из `TEAM_USER_IDS` в том же треде
- Формат: `Hey @user1 @user2, waiting for your update! ⏳`

### Error Handling
- Все внешние вызовы (Slack API, Supabase) обёрнуты в try/except
- Бот продолжает работать при ошибках отдельных операций
- Логирование через Python logging

---

## Database Schema

**Table: `standup_reports`**

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| user_id | text | Slack user ID |
| date | date | Report date (default: today) |
| raw_text | text | Full message text |
| thread_ts | text | Message timestamp |
| created_at | timestamptz | UTC creation time |

**Table: `bot_state`** (runtime)

| Column | Type | Description |
|--------|------|-------------|
| key | text | State key (e.g. `daily_thread_ts`) |
| value | text | State value |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | ✅ | Bot User OAuth Token (xoxb-...) |
| `SLACK_APP_TOKEN` | ✅ | App-Level Token for Socket Mode (xapp-...) |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_KEY` | ✅ | Supabase anon/service key |
| `CHANNEL_ID` | ✅ | Target Slack channel ID |

---

## Test Coverage

**43 tests across 10 test suites:**

| Suite | Tests | Coverage |
|-------|-------|----------|
| TC-01: Configuration | 5 | Env vars, initial state |
| TC-02: Supabase Client | 2 | Init with/without creds |
| TC-03: post_daily_thread | 7 | Posting, channel, ts, phrases, errors |
| TC-04: check_missing_reports | 5 | Missing users, pings, edge cases |
| TC-05: handle_message_events | 7 | Save, react, filter, errors |
| TC-06: phrases.py | 3 | Format, content validation |
| TC-07: post_daily_thread ext. | 4 | Instructions, state persistence |
| TC-08: check_missing_reports ext. | 4 | Emoji, thread, date queries |
| TC-09: handle_message edge cases | 3 | No thread_ts, no supabase, error rollback |
| TC-10: main() init | 3 | Token check, app init, scheduler |

Run: `python -m pytest test_bot.py -v`

---

## Maintenance Notes

### Phrases & Memes
- **MEMES** (reminder GIFs/phrases) and **MICHAEL_SCOTT_GREETINGS** in `main.py` should be reviewed and updated periodically — Giphy links can expire or become unavailable over time.
- All user-facing text must be in **English only**.
- **Next iteration:** phrase and meme generation will be handled via AI to keep content fresh automatically.

---

## Known Limitations (MVP)

- `TEAM_USER_IDS` is hardcoded — needs dynamic loading from Slack/Supabase
- No web dashboard (frontend in scaffolding)
- No bot slash commands (/standup, /skip, /summary)
- No analytics or report trends
- Single-channel only

---

## Deployment

**Current:** Replit (autoscale)
**Recommended free tier:** Railway.app / Render.com / Fly.io

See `DEPLOY.md` for step-by-step instructions.

---

## Roadmap (v0.2.0+)

- [ ] Dynamic team roster from Slack channel members
- [ ] Slash commands (/standup, /skip, /summary)
- [ ] Weekly digest with analytics
- [ ] Web dashboard for report history
- [ ] Multi-channel support
- [ ] Timezone-aware scheduling
