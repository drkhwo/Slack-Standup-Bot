# Deploy Guide — Railway

## Prerequisites

Before deploying, make sure the following are ready:

1. A Railway account with access to the target project
2. A Slack app with Socket Mode enabled
3. A Supabase project with `standup_reports` created from `setup.sql`
4. A `bot_state` table for storing `daily_thread_ts`
5. Repository access to this project

## Required environment variables

Configure these in the Railway service:

```text
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
CHANNEL_ID=C1234567890
```

Optional variables:

```text
VACATION_TRACKER_API_KEY=...
ALERT_CHANNEL_ID=C1234567890
DEPLOY_NOTIFY=1
```

`DEPLOY_NOTIFY=1` is intended for a one-time deploy confirmation. Remove it after a successful deployment if you do not want deploy alerts on later restarts.

## Local verification before deploy

Run the regression suite:

```bash
python -m pytest test_bot.py -v
```

## Deploy options

### Option 1: Git-driven deploy

If the Railway service is connected to the GitHub repository:

```bash
git add main.py phrases.py test_bot.py AGENTS.md MANIFEST.md DEPLOY.md
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
5. A reply in the thread is saved and receives a `blue_heart` reaction
6. The bot posts reminders at `11:30` and `17:00 Europe/Paris`
7. If someone is still missing at `21:00 Europe/Paris`, the bot posts the final escalation in the same thread and tags `@dk`

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

- Verify Supabase connectivity and credentials
- Verify `standup_reports` exists
- Verify the service role or RLS policies allow reads and writes

### Thread recovery after restart fails

- Verify the `bot_state` table exists
- Verify the bot can read and write the `daily_thread_ts` record

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
