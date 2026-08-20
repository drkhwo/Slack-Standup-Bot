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
4. `handle_message_events()` listens for replies in the tracked threads, ignores bot messages, writes or updates the user's report in `standup_reports` (daily thread) or `weekly_reports` (Friday weekly thread), and adds one random approved reaction from the 17-alias set after a successful database write.
5. `check_missing_reports()` loads today's reporters from Supabase, subtracts users who are out, and uploads one of the 12 manifest-backed local Monkey Business assets with the daytime reminder for anyone still missing.
6. `post_end_of_day_escalation()` posts a final same-thread escalation at `21:00 Europe/Paris` if anyone is still missing, tagging only `@dk`.
7. On Fridays `post_weekly_thread()` posts a second, separate thread for weekly updates and links to it from the daily thread. While that thread is live, the daily reminder, personal DM, and end-of-day escalation return early — the daily thread stays open but optional. `check_missing_weekly_reports()`, `post_weekly_thread_closed()`, and `post_weekly_escalation()` then work the weekly thread on its own schedule, each refusing to touch a thread that is not from today. Every relaxation and every weekly job is gated on `_weekly_thread_is_today()`, so a failed 09:06 post degrades to the ordinary daily flow plus an alert rather than to silence. `WEEKLY_UPDATES=0` disables all of this, including the reply routing into `weekly_reports`.

### Scheduler configuration

Current jobs are configured directly in `main.py`:

- Timezone: `Europe/Paris`
- Daily standup thread: weekdays at `09:04`
- Personal reminder DM: weekdays at `09:15`
- Missing-report reminder: weekdays at `12:30`
- Thread-closed message: weekdays at `13:01`
- End-of-day escalation: weekdays at `21:00`
- Weekly update thread: Fridays at `09:06`
- Weekly missing-update reminder: Fridays at `16:30`
- Weekly thread-closed message: Fridays at `18:01`
- Weekly escalation: Fridays at `18:30`

The bot uses `files_upload_v2` with the `files:write` Slack bot scope for reminder and escalation media. If an upload fails, it posts the same copy as a text-only reply in the active thread.

Reaction-only aliases are separate from media aliases: `pink-monke`, `monkey-zen`, `omg-monkey`, `matrix-code`, and `matrix-monitors` can confirm saved reports but are not media-upload candidates because they have no manifest files.

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

### `weekly_reports`

Defined in `setup.sql` with the same shape as `standup_reports`, used for one weekly update per user per Friday. Repeat replies are appended the same way.

### `bot_state`

The bot also expects a `bot_state` key/value table for persistence of `daily_thread_ts` and `weekly_thread_ts` across restarts.

Expected shape:

- `key` — text primary key or unique key
- `value` — text

Required record:

- `key = daily_thread_ts`

## Team membership

`TEAM_MAPPING` in `main.py` maps active Slack user IDs to Vacation Tracker identity records (`vt_user_id`, `name`, and `email`).

`DEACTIVATED_USER_IDS` is a manual fallback for Slack accounts that are no longer active but may still exist in stale roster data. `TEAM_USER_IDS` is derived from `TEAM_MAPPING`, excludes the CEO (`U068KKKNP9R`), and always excludes IDs in `DEACTIVATED_USER_IDS`. When the team changes, update `TEAM_MAPPING` and keep `DEACTIVATED_USER_IDS` current.

### Removing someone who has left

Do all three steps — the first two are deliberately redundant, so that a stale entry restored to `TEAM_MAPPING` by mistake still cannot put the person back on the roster:

1. Delete their record from `TEAM_MAPPING`.
2. Add their Slack ID to `DEACTIVATED_USER_IDS`, with their name as a trailing comment.
3. Add the ID to the `deactivated_user_ids` set in TC-01-07 (`test_bot.py`), which asserts the ID is in `DEACTIVATED_USER_IDS` and absent from both `TEAM_MAPPING` and `TEAM_USER_IDS`.

Then redeploy. Until the deploy lands, the running instance keeps the old roster and will still ping them.

Someone who is merely away — on leave or otherwise temporarily absent — stays in `TEAM_MAPPING` untouched; Vacation Tracker handles that case at runtime.

## Operational notes

- The bot relies on a single active process. Running multiple instances can create duplicate daily threads and duplicate reminders.
- `send_alert()` mirrors operational notifications to `ALERT_CHANNEL_ID` when configured.
- `send_deploy_notification()` only sends a deploy alert when `DEPLOY_NOTIFY=1` is present in the environment.
- Random motivational boost messages are no longer part of the production flow.
- End-of-day escalation posts in the main standup thread, not in `ALERT_CHANNEL_ID`.

## Deployment

`Dockerfile` and `railway.toml` deploy `main.py` on Railway.

See `DEPLOY.md` for deployment and verification steps.
