# Slack Standup Bot — Project Manifest

**Version:** 0.3.0
**Updated:** 2026-04-02

## Overview

Slack Standup Bot automates a daily Slack status thread for a fixed team roster. It posts the thread, collects replies, persists reports in Supabase, marks confirmed messages with a reaction, checks Vacation Tracker to avoid false reminders, posts daytime reminders for missing updates, and escalates unresolved missing reports at the end of the day.

## Architecture

```text
Slack Socket Mode events
        |
        v
   Python bot (`main.py`)
    |       |        |
    |       |        +--> Vacation Tracker API
    |       |
    |       +------------> APScheduler cron jobs
    |
    +--------------------> Supabase
```

**Tech stack:** Python, Slack Bolt, Supabase, APScheduler, requests, Railway

## Runtime behavior

### Daily thread posting

- Posts one standup prompt to `CHANNEL_ID`
- Uses a random opening phrase from `phrases.py`
- Persists the returned Slack thread timestamp in memory and in Supabase
- Posts a same-thread vacation status message immediately after the main prompt

### Report collection

- Listens for Slack `message` events
- Accepts only replies that belong to the active `daily_thread_ts`
- Ignores bot-authored messages
- Inserts a new `standup_reports` row for the first reply of the day
- Appends later replies from the same user to the existing `raw_text`
- Adds a `blue_heart` reaction only after the database write succeeds

### Missing report reminders

- Loads today's reports from Supabase
- Loads approved absences from Vacation Tracker
- Excludes users on leave from reminder targeting
- Posts a reminder in the existing standup thread for anyone still missing

### End-of-day escalation

- Runs a final check at the end of the workday
- Reuses the same missing-user calculation as the daytime reminders
- Posts in the existing standup thread only when users are still missing
- Tags only `@dk`
- Includes a dramatic sad GIF for visibility

### Scheduling

Configured in `main.py`:

Timezone: `Europe/Paris`

- Weekdays at `09:04` — post daily thread
- Weekdays at `11:30` — first reminder
- Weekdays at `17:00` — second reminder
- Weekdays at `21:00` — final missing-report escalation

## Database

### `standup_reports`

Current schema in `setup.sql`:

| Column | Type | Description |
|---|---|---|
| `id` | `uuid` | Primary key |
| `user_id` | `text` | Slack user ID |
| `date` | `date` | Report date |
| `raw_text` | `text` | Full stored report body |
| `thread_ts` | `text` | Slack message timestamp |
| `created_at` | `timestamptz` | Record creation time |

### `bot_state`

The bot also expects a `bot_state` key/value table for restart recovery of `daily_thread_ts`.

Suggested structure:

| Column | Type | Description |
|---|---|---|
| `key` | `text` | State key |
| `value` | `text` | Stored value |

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot token |
| `SLACK_APP_TOKEN` | Yes | Socket Mode app token |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase API key |
| `CHANNEL_ID` | Yes | Slack channel for standups |
| `VACATION_TRACKER_API_KEY` | No | Enables leave checks |
| `ALERT_CHANNEL_ID` | No | Sends monitoring alerts |
| `DEPLOY_NOTIFY` | No | Sends one deploy alert when set to `1` |

## Testing

Regression tests live in `test_bot.py`.

Run:

```bash
python -m pytest test_bot.py -v
```

Current verified suite size: `66` tests.

## Operational notes

- Only one bot instance should run at a time.
- `TEAM_MAPPING` and `DEACTIVATED_USER_IDS` are hardcoded and must be kept current when the roster changes or a Slack account is deactivated.
- Vacation Tracker matching prefers stable Vacation Tracker user ID, then user email, and falls back to normalized display names.
- The repository still contains scaffolded `client/` and `server/` folders that are not part of the live bot.
- Random motivational GIF or quote messages are no longer part of the production behavior.
- End-of-day escalation stays in the standup thread and does not write to `ALERT_CHANNEL_ID`.

## Known limitations

- Team membership is static in code.
- The bot supports one primary standup channel.
- There are no slash commands or admin controls.
- There is no dashboard for browsing historical reports.

## Deployment

Railway uses the `Dockerfile` build and starts the service with:

```bash
python main.py
```

See `DEPLOY.md` for the current deployment procedure.
