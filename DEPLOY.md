# Deploy Guide — Railway

## Prerequisites

Before deploying, make sure the following are ready:

1. A Railway account with access to the target project
2. A Slack app with Socket Mode enabled
3. A Supabase project with `standup_reports` created from `setup.sql`
4. A `bot_state` table for storing `daily_thread_ts` and `weekly_thread_ts`
5. A `weekly_reports` table for the Friday weekly updates — see [Supabase migration](#supabase-migration-weekly_reports)
6. Repository access to this project

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
SKIP_TODAY=1
WEEKLY_UPDATES=0
```

`WEEKLY_UPDATES` is a kill switch, not a feature flag: leave it unset and the Friday weekly-update thread runs. Set it to `0` to go back to daily-only behaviour — no weekly thread, no weekly reminders, and Friday's daily reminder, personal DM, and end-of-day escalation behave exactly as they do Monday through Thursday. Any value other than `0` (including an unset variable) means the weekly flow is active.

`DEPLOY_NOTIFY=1` is intended for a one-time deploy confirmation. Remove it after a successful deployment if you do not want deploy alerts on later restarts.

## Supabase migration: `weekly_reports`

The Friday weekly-update thread stores replies in their own table. Without it the bot still posts and still nudges people — the roster check falls back to reading the Slack thread — but every write fails with `PGRST205` in the logs and no update is recorded. Run this before merging the weekly-update change.

### How the connection works

The bot only ever talks to Supabase through two environment variables set on the Railway service, `SUPABASE_URL` and `SUPABASE_KEY` (see `get_supabase_client()` in `main.py`). There is no connection string, no pooler, and no migration tool in the loop — `supabase-py` calls the project's REST API over HTTPS. Nothing about the connection changes when you add a table; the new table just has to be reachable by the same key.

That key is the project's **anon** key, not a service-role key. So the new table has to be readable and writable by the `anon` role, exactly like `standup_reports` is today. This is why the table must be created from the SQL editor.

> **Do not create this table from the Table Editor UI.** The UI enables Row Level Security on new tables by default. With RLS on and no policies, reads silently return zero rows and writes fail — the bot keeps running and the breakage only shows up as missing data. `create table` from the SQL editor leaves RLS off, matching `standup_reports`.

### Steps

1. Open the Supabase dashboard for the project referenced by `SUPABASE_URL`, then **SQL Editor → New query**.

2. Paste the `weekly_reports` block from `setup.sql`:

   ```sql
   create table weekly_reports (
     id uuid default gen_random_uuid() primary key,
     user_id text not null,
     date date not null default current_date,
     raw_text text not null,
     thread_ts text not null,
     created_at timestamp with time zone default timezone('utc'::text, now()) not null
   );
   ```

3. Run it. Expected result: `Success. No rows returned`.

4. Confirm the table is reachable with the key the bot actually uses. From the repo root, with the Railway CLI linked (`railway status` shows the `SlackBot` service), this borrows the deployed variables without ever writing them to disk:

   ```bash
   railway run python -c "
   import os
   from supabase import create_client
   client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])
   probe = {'user_id': 'PROBE', 'date': '1970-01-01', 'raw_text': 'probe', 'thread_ts': '0'}
   client.table('weekly_reports').insert(probe).execute()
   print('insert ok:', client.table('weekly_reports').select('*').eq('user_id', 'PROBE').execute().data)
   client.table('weekly_reports').delete().eq('user_id', 'PROBE').execute()
   print('after cleanup:', client.table('weekly_reports').select('*').eq('user_id', 'PROBE').execute().data)
   "
   ```

   Expected: `insert ok:` prints one row, `after cleanup:` prints `[]`. A `PGRST205` means the table is not there (wrong project, or the query never ran). A `42501` or an empty `insert ok:` means RLS is on — see below.

5. Deploy. `WEEKLY_UPDATES` does not need to be set: unset means active.

### If RLS ended up enabled

Either turn it off so the table matches `standup_reports`:

```sql
alter table weekly_reports disable row level security;
```

Or keep it on and grant the `anon` role what the bot needs — it inserts, selects, and updates rows:

```sql
alter table weekly_reports enable row level security;

create policy "bot reads weekly reports" on weekly_reports
  for select to anon using (true);

create policy "bot writes weekly reports" on weekly_reports
  for insert to anon with check (true);

create policy "bot appends to weekly reports" on weekly_reports
  for update to anon using (true) with check (true);
```

Re-run the probe in step 4 afterwards.

### Rolling the table back

Dropping it is safe once `WEEKLY_UPDATES=0` is set and the service has restarted:

```sql
drop table weekly_reports;
```

Do it in that order. With the weekly flow still active, a dropped table means a `PGRST205` on every Friday reply.

## Local verification before deploy

Run the regression suite:

```bash
python -m pytest test_bot.py -v
```

## Deploy options

### Option 1: Git-driven deploy

If the Railway service is connected to the GitHub repository:

```bash
git add .dockerignore Dockerfile main.py phrases.py test_bot.py AGENTS.md CLAUDE.md MANIFEST.md DEPLOY.md COPY_PROPOSAL_REVISED.md SLACK_APP_PROFILE_CHECK.md assets/monkey-business
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
2. A reply in the weekly thread gets a reaction, and a row shows up in `weekly_reports` for that user and date
3. `12:30` and `21:00` — **no** daily reminder and **no** daily escalation; the logs read `Friday: the daily thread is optional`
4. `13:01` — the daily close message ends with `The weekly update thread stays open until 18:00.`
5. `16:30` — only people with no weekly update are pinged, inside the weekly thread
6. `18:01` and `18:30` — the weekly thread is closed, and anyone still missing is escalated to `@dk`

Before exercising reminder or escalation media, verify that the installed bot token has the `files:write` scope. The bot uploads local GIF/PNG assets from `assets/monkey-business/` with the copy in `initial_comment`; upload failures fall back to a text-only thread reply.

The five reaction-only aliases (`pink-monke`, `monkey-zen`, `omg-monkey`, `matrix-code`, and `matrix-monitors`) are not upload candidates because they are not present in the media manifest.

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

### Weekly updates are not saved

- Verify `weekly_reports` exists and that the probe in [Supabase migration](#supabase-migration-weekly_reports) passes
- Look for `PGRST205` (table missing) or `42501` (RLS blocking) in the Railway logs
- Confirm `WEEKLY_UPDATES` is not set to `0`

### No weekly thread appeared on Friday

- Confirm `WEEKLY_UPDATES` is not `0` and `SKIP_TODAY` is not `1`
- Check the logs for `Posted weekly thread` at `09:06 Europe/Paris`
- If reminders were skipped with `No weekly thread from today`, the `09:06` post failed: the weekly jobs deliberately refuse to touch a thread that is not from today, so last week's thread never gets stray pings

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
