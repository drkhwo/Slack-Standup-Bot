# Deploy Guide — Railway.app

## Prerequisites

1. GitHub аккаунт с репозиторием проекта
2. Railway аккаунт (railway.app) — залогиниться через GitHub
3. Slack App с Socket Mode (токены уже должны быть)
4. Supabase проект с таблицей `standup_reports` (см. `setup.sql`)

---

## Step 1: Push to GitHub

```bash
git add Dockerfile railway.toml Procfile .dockerignore
git commit -m "Add Railway deployment config"
git push origin main
```

## Step 2: Create Railway Project

1. Открой https://railway.app/new
2. Выбери **"Deploy from GitHub Repo"**
3. Подключи репозиторий `Slack-Standup-Bot`
4. Railway автоматически обнаружит `Dockerfile`

## Step 3: Set Environment Variables

В Railway dashboard -> твой сервис -> **Variables**, добавь:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
CHANNEL_ID=C08UT7VP2TA
```

## Step 4: Deploy

Railway задеплоит автоматически после добавления переменных.

Проверь логи в Railway dashboard — должно быть:
```
Bot started!
```

## Step 5: Verify

1. Подожди до 09:00 (или временно измени cron в main.py для теста)
2. Проверь Slack канал — бот должен создать тред
3. Ответь в треде — должна появиться реакция

---

## Troubleshooting

**Bot не запускается:**
- Проверь что все 5 переменных заданы в Railway Variables
- Посмотри логи: Railway dashboard -> Deployments -> View Logs

**No daily thread:**
- Убедись что `CHANNEL_ID` правильный
- Бот должен быть приглашён в канал (`/invite @bot-name`)

**Supabase errors:**
- Проверь что таблица `standup_reports` создана (см. `setup.sql`)
- Проверь что RLS policies позволяют insert/select

---

## Useful Commands

```bash
# Установить Railway CLI
npm install -g @railway/cli

# Залогиниться
railway login

# Деплой из CLI
railway up

# Посмотреть логи
railway logs
```

## Costs

Railway free tier: $5 credit/month (достаточно для 24/7 Python бота).
Supabase free tier: 500MB database, 50K requests/month.
