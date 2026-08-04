# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Slack standup bot deployed on Railway. It posts a daily thread to a Slack channel, tracks who has replied, reminds missing reporters, and checks the Vacation Tracker API to exclude people on leave.

The repo also contains a scaffolded (mostly empty) Express/React/TypeScript web app (`server/`, `client/`) that is not currently used by the bot.

## Running the bot locally

```bash
source .venv/bin/activate
python main.py
```

Required `.env` variables:
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SUPABASE_URL=https://...supabase.co
SUPABASE_KEY=...
CHANNEL_ID=C...
VACATION_TRACKER_API_KEY=...   # optional
ALERT_CHANNEL_ID=C...          # optional: mirror alerts to a monitoring channel
DEPLOY_NOTIFY=1                # optional: send deploy notification on startup (set once, then remove)
SKIP_TODAY=1                   # optional: set to "1" to suppress all reminders for the day; any other value (including "0") means normal operation
```

## Running tests

```bash
source .venv/bin/activate
python -m pytest test_bot.py -v
# or a single test class:
python -m pytest test_bot.py::TestPostDailyThread -v
```

Tests mock all external dependencies (Slack, Supabase, APScheduler) at module load time.

## Architecture

**Python bot (the live service):**

- `main.py` — all bot logic: Slack app init, APScheduler jobs, Supabase reads/writes, Vacation Tracker API calls
- `phrases.py` — list of randomised opening phrases for the daily thread
- `test_bot.py` — unittest suite (TC-01 through TC-11) covering all bot functions

**Cron schedule (Europe/Paris timezone, weekdays only):**
| Time  | Function                    | Description                                      |
|-------|-----------------------------|--------------------------------------------------|
| 09:04 | `post_daily_thread()`       | Posts standup prompt + vacation status in-thread |
| 09:15 | `send_personal_standup_reminder()` | Sends the configured personal reminder DM |
| 12:30 | `check_missing_reports()`   | Reminder to people who haven't reported         |
| 13:01 | `post_thread_closed()`      | Closes the active standup thread                |
| 21:00 | `post_end_of_day_escalation()` | Escalation to CEO if anyone still missing     |

**Key data flows:**
1. `post_daily_thread()` posts the standup prompt to `CHANNEL_ID`, saves the returned thread `ts` to `daily_thread_ts` global and the `bot_state` Supabase table so it survives restarts.
2. `handle_message_events()` listens for replies in that thread. Each persisted reply gets one random reaction from the approved 17-alias set. Subsequent replies from the same user on the same day are appended to the existing record.
3. `check_missing_reports()` queries `standup_reports` for today's date, cross-references `TEAM_USER_IDS` and vacation data, then uploads one of the 12 manifest-backed local Monkey Business media files with the reminder in-thread, falling back to text if the upload fails.
4. `post_end_of_day_escalation()` does the same check but pings the CEO (`U068KKKNP9R`) if anyone is still missing.
5. `get_vacation_users()` calls `https://api.vacationtracker.io/v1/leaves` with pagination, maps Vacation Tracker users to Slack IDs via `TEAM_MAPPING`, returns a set of absent UIDs or `"error"` on failure.

**Supabase tables:**
- `standup_reports` — one row per user per day (`user_id`, `date`, `raw_text`, `thread_ts`); see `setup.sql`
- `bot_state` — key/value store for `daily_thread_ts` persistence across restarts

**Deployment:** Dockerfile + `railway.toml` deploy `main.py` on Railway. See `DEPLOY.md` for setup steps.

**Team membership:** `TEAM_MAPPING` in `main.py` maps active Slack user IDs to Vacation Tracker identity records (`vt_user_id`, `name`, and `email`). `DEACTIVATED_USER_IDS` is the manual fallback for deactivated Slack accounts. `TEAM_USER_IDS` derives from the mapping, excluding the CEO (`U068KKKNP9R`) and all deactivated IDs. To add/remove a team member: edit `TEAM_MAPPING`, update `DEACTIVATED_USER_IDS` when needed, and redeploy.

**Skipping reminders for a day:** Set `SKIP_TODAY=1` in Railway env vars. Important: `SKIP_TODAY=0` does NOT skip — only the value `"1"` does. Remove or set to `0` to resume normal operation.

**Reaction/media aliases:** The runtime has 17 approved reaction aliases. Only the 12 aliases present in `assets/monkey-business/manifest.json` are eligible for reminder and escalation uploads.

**Test lines:** The two calls at the end of `main()` (`post_daily_thread()` / `check_missing_reports()`) are test/dry-run lines — comment them out for normal production operation.
