# Dailyder Bot

`Dailyder Bot` is a production-oriented Telegram bot for collecting morning daily plans and evening status updates from a mobile team.

## Stack

- Python 3.12
- aiogram 3.x
- SQLAlchemy 2.x
- PostgreSQL
- APScheduler
- Fly.io

## Main flows

- `09:00` on workdays: send AM digest to the group and private reminders to onboarded developers.
- Developers submit tasks in a strict text template.
- `17:00` on workdays: send PM digest to the group and private reminders for status updates.
- Developers update each morning task with `✅ / ⚠️ / 🚫 / 🪓` and an optional final note.
- Admins manage binding, reminders, pending users, and metrics directly from Telegram.

## Local run

1. Create a virtualenv and install dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

2. Copy `.env.example` to `.env` and fill real values.

3. Run database migrations:

```bash
python -m dailyder_bot.db.migrate
```

4. Start the bot:

```bash
python -m dailyder_bot
```

## Telegram setup

1. Create a bot with `@BotFather`.
2. Add the bot to your supergroup as admin.
3. Set `ADMIN_USER_IDS` to your Telegram user IDs.
4. Run `/bind_group` inside the target supergroup once.
5. Ask developers to open a private chat with the bot and send `/start`.

## Fly.io deploy

1. Create a Fly app and Fly Postgres cluster.
2. Attach the Postgres database and set secrets:

```bash
fly secrets set BOT_TOKEN=... DATABASE_URL=... ADMIN_USER_IDS=111111111
```

3. Deploy:

```bash
fly deploy -a dailyder-bot
```

4. Verify the health check:

```bash
fly status
```

## Operations

- Run a single machine only. The bot uses long polling, so multiple active instances will duplicate updates and reminder delivery.
- `fly.toml` runs migrations before each deploy with `release_command = 'python -m dailyder_bot.db.migrate'`.
- The health check is `GET /healthz` and fails if the database is unreachable.
- Application logs go to stdout/stderr. Use `fly logs -a dailyder-bot` for live inspection and `fly logs -a dailyder-bot -n 200` for recent history.
- If the bot stops answering, check this order: health check status, Postgres connectivity, bot token validity, then Telegram rate limits.
- Keep `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_USER_IDS`, `TIMEZONE`, `HASHTAG`, `AM_REMINDER_TIME`, `PM_REMINDER_TIME`, and `PORT` aligned across environments.
- After schema changes, verify the release command completed successfully before promoting traffic or scaling the machine back up.

## Notes

- The bot uses long polling, so run a single app instance.
- `GROUP_CHAT_ID` can be configured by env or via `/bind_group`.
- History retention is 30 days and is cleaned automatically by a scheduled job.
