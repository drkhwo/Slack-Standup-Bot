# Deploy Guide — Railway

## Prerequisites

Before deploying, make sure the following are ready:

1. A Railway account with access to the target project
2. A Slack app with Socket Mode enabled
3. A Postgres database with `standup_reports`, `weekly_reports` and `bot_state` created from `setup.sql` — see [Database](#database)
4. Repository access to this project

## Required environment variables

Configure these in the Railway service:

```text
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
DATABASE_URL=postgresql://user:pass@host:5432/standup
CHANNEL_ID=C1234567890
```

Optional variables:

```text
VACATION_TRACKER_API_KEY=...
ALERT_CHANNEL_ID=C1234567890
DEPLOY_NOTIFY=1
SKIP_TODAY=1
WEEKLY_UPDATES=0
```

`WEEKLY_UPDATES` is a kill switch, not a feature flag: leave it unset and the Friday weekly-update thread runs. Set it to `0` to go back to daily-only behaviour — no weekly thread, no weekly reminders, and Friday's daily reminder, personal DM, and end-of-day escalation behave exactly as they do Monday through Thursday. Any value other than `0` (including an unset variable) means the weekly flow is active.

`DEPLOY_NOTIFY=1` is intended for a one-time deploy confirmation. Remove it after a successful deployment if you do not want deploy alerts on later restarts.

## Database

The bot stores reports and thread state in Postgres, reached through one connection string, `DATABASE_URL` (see `get_supabase_client()` and `db.py`). `setup.sql` creates all three tables — `standup_reports`, `weekly_reports` and `bot_state`:

```bash
psql "$DATABASE_URL" -f setup.sql
```

Without `weekly_reports` the Friday thread still posts and closes, but nothing is recorded and the 16:30 reminder and 18:30 escalation log an error and return.

## Local verification before deploy

Run the regression suite:

```bash
python -m pytest test_bot.py -v
```

## Deploy options

### Option 1: Git-driven deploy

If the Railway service is connected to the GitHub repository:

```bash
git add .dockerignore Dockerfile main.py phrases.py test_bot.py AGENTS.md CLAUDE.md MANIFEST.md DEPLOY.md SLACK_APP_PROFILE_CHECK.md assets/iroh
git commit -m "Add end-of-day missing report escalation"
git push origin main
```

Railway will build and deploy from the pushed commit.

### Option 2: Railway CLI deploy

If you want to deploy directly from the current working tree:

```bash
railway link
railway up
```

This deploys the current local state without requiring a Git push.

## Post-deploy checks

After deployment, verify the following:

1. Service starts successfully and logs `Bot started!`
2. The bot connects to Slack Socket Mode without authentication errors
3. The scheduler runs in `Europe/Paris` local time
4. The next scheduled standup thread appears in the configured channel at `09:04 Europe/Paris`
5. A saved reply receives one of the 17 approved reactions
6. The bot posts the missing-report reminder at `12:30 Europe/Paris` and closes the thread at `13:01 Europe/Paris`
7. If someone is still missing at `21:00 Europe/Paris`, the bot posts the final escalation in the same thread and tags `@dk`

On the first Friday after deploying the weekly-update change, also verify:

1. `09:06` — a second, standalone message appears in the channel (not a reply), and a pointer reply with a link to it appears in the daily thread
2. A reply in the weekly thread gets **no** reaction, and a row shows up in `weekly_reports` for that user and date
3. `12:30` and `21:00` — **no** daily reminder and **no** daily escalation; the logs read `Weekly thread is live — the daily thread is optional today`
4. `13:01` — the daily close message ends with `The weekly thread stays open until 18:00 — there is still time for one more cup.`
5. `16:30` — only people with no weekly update are pinged, inside the weekly thread
6. `18:01` and `18:30` — the weekly thread is closed, and anyone still missing is escalated to `@dk`

If the `09:06` post ever fails, none of the Friday relaxations apply: the daily reminder, personal DM, and end-of-day escalation run exactly as they do on any other weekday, and an alert goes to `ALERT_CHANNEL_ID`. Friday is never left without any nudge at all.

Before exercising reminder or escalation media, verify that the installed bot token has the `files:write` scope. The bot uploads local GIF/PNG assets from `assets/iroh/` with the copy in `initial_comment`; upload failures fall back to a text-only thread reply.

Reaction aliases are workspace custom emoji and are not upload candidates; uploads use only the aliases in the media manifest.

## Troubleshooting

### Bot does not start

- Confirm all required environment variables are set
- Check the Railway deployment logs
- Verify the Slack bot token and app token belong to the same Slack app

### No daily thread appears

- Confirm `CHANNEL_ID` points to the correct Slack channel
- Confirm the bot user is invited to that channel
- Confirm the scheduler is running and the service stays up between cron times
- Confirm the service clock is using the intended `Europe/Paris` scheduler timezone

### Reports are not saved

- Verify `DATABASE_URL` and that the database is reachable from the service
- Verify `standup_reports` exists

### Weekly updates are not saved

- Verify `weekly_reports` exists (see [Database](#database))
- Look for `relation "weekly_reports" does not exist` in the logs
- Confirm `WEEKLY_UPDATES` is not set to `0`

### No weekly thread appeared on Friday

- Confirm `WEEKLY_UPDATES` is not `0` and `SKIP_TODAY` is not `1`
- Check the logs for `Posted weekly thread` at `09:06 Europe/Paris`, and `ALERT_CHANNEL_ID` for `Could not post this week's update thread`
- If reminders were skipped with `No weekly thread from today`, the `09:06` post failed: the weekly jobs deliberately refuse to touch a thread that is not from today, so last week's thread never gets stray pings — and the daily reminders take over for that day

### Thread recovery after restart fails

- Verify the `bot_state` table exists
- Verify the bot can read and write the `daily_thread_ts` and `weekly_thread_ts` records

### Vacation status is missing

- Confirm `VACATION_TRACKER_API_KEY` is set
- Check logs for Vacation Tracker API errors

### End-of-day escalation did not fire

- Confirm there were still missing reports at `21:00 Europe/Paris`
- Confirm `daily_thread_ts` was restored or created correctly for that day
- Check logs for `Error posting end-of-day escalation`

## Useful commands

```bash
railway whoami
railway status
railway link
railway up
railway logs
```
