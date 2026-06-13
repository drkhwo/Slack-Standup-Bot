# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working in this repository.

## What this is

A Slack standup bot deployed on Railway. It posts a daily thread to a Slack channel, tracks who has replied, reminds missing reporters, posts an end-of-day escalation for missing updates, and checks the Vacation Tracker API to exclude people who are out.

The repository also contains a scaffolded Express/React/TypeScript web app in `server/` and `client/`, but that app is not part of the live bot flow.

## Running the bot locally

```bash
source .venv/bin/activate
python main.py
```

Required `.env` variables:

```text
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SUPABASE_URL=https://...supabase.co
SUPABASE_KEY=...
CHANNEL_ID=C...
VACATION_TRACKER_API_KEY=...   # optional
ALERT_CHANNEL_ID=C...          # optional
DEPLOY_NOTIFY=1                # optional, only for one-time deploy alerts
```

## Running tests

```bash
source .venv/bin/activate
python -m pytest test_bot.py -v
python -m pytest test_bot.py::TestPostDailyThread -v
```

Tests mock Slack, Supabase, APScheduler, and dotenv imports at module load time.

## Production architecture

### Live Python bot

- `main.py` — application bootstrap, scheduler jobs, Slack event handling, Supabase persistence, Vacation Tracker integration
- `phrases.py` — randomized opening phrases for the daily standup thread
- `test_bot.py` — regression tests for bot behavior

### Main runtime flow

1. `main()` initializes the Slack Bolt app, Supabase client, background scheduler, and message event handler.
2. `post_daily_thread()` posts the daily standup message to `CHANNEL_ID`, stores the returned Slack timestamp in the in-memory `daily_thread_ts` variable, and persists it into the `bot_state` table.
3. `post_daily_thread()` immediately posts a vacation status reply in the same thread based on `get_vacation_users()`.
4. `handle_message_events()` listens for replies in the active daily thread, ignores bot messages, writes or updates the user's report in `standup_reports`, and adds a `blue_heart` reaction after a successful database write.
5. `check_missing_reports()` loads today's reporters from Supabase, subtracts users who are out, and posts daytime reminders for anyone still missing.
6. `post_end_of_day_escalation()` posts a final same-thread escalation at `21:00 Europe/Paris` if anyone is still missing, tagging only `@dk`.

### Scheduler configuration

Current jobs are configured directly in `main.py`:

- Timezone: `Europe/Paris`
- Daily standup thread: weekdays at `09:04`
- First reminder: weekdays at `11:30`
- Second reminder: weekdays at `17:00`
- End-of-day escalation: weekdays at `21:00`

These values come from APScheduler cron jobs in code and should be treated as the source of truth.

### Vacation Tracker integration

`get_vacation_users()` calls `https://api.vacationtracker.io/v1/leaves`, follows `nextToken` pagination, filters for `APPROVED` leave records, and maps Vacation Tracker users to Slack IDs using `TEAM_MAPPING`. Matching prefers stable Vacation Tracker user ID, then Vacation Tracker email, and falls back to normalized display name.

If the API call fails, the function returns `"error"` and the bot continues operating without blocking standup collection.

## Database

### `standup_reports`

Defined in `setup.sql` and used for one report per user per day:

- `user_id`
- `date`
- `raw_text`
- `thread_ts`

If a user replies more than once on the same day, the new text is appended to the existing `raw_text` field.

### `bot_state`

The bot also expects a `bot_state` key/value table for persistence of `daily_thread_ts` across restarts.

Expected shape:

- `key` — text primary key or unique key
- `value` — text

Required record:

- `key = daily_thread_ts`

## Team membership

`TEAM_MAPPING` in `main.py` maps Slack user IDs to Vacation Tracker identity records (`vt_user_id`, `name`, and `email`).

`TEAM_USER_IDS` is derived from that mapping and excludes the CEO (`U068KKKNP9R`). When the team changes, update `TEAM_MAPPING` and verify that the excluded user logic is still correct.

## Operational notes

- The bot relies on a single active process. Running multiple instances can create duplicate daily threads and duplicate reminders.
- `send_alert()` mirrors operational notifications to `ALERT_CHANNEL_ID` when configured.
- `send_deploy_notification()` only sends a deploy alert when `DEPLOY_NOTIFY=1` is present in the environment.
- Random motivational boost messages are no longer part of the production flow.
- End-of-day escalation posts in the main standup thread, not in `ALERT_CHANNEL_ID`.

## Deployment

`Dockerfile` and `railway.toml` deploy `main.py` on Railway.

See `DEPLOY.md` for deployment and verification steps.
