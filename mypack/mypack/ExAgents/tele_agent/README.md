# tele_agent

A notifier agent: sends messages and files to Telegram using the `tele_tool` ExTool.
The planner routes Telegram requests to it via its `task_types`.

Requires:
  - the `tele_tool` ExTool (registered in this pack)
Env:
  - TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  → set in `ExAgents/tele_agent/.env`
    (see `.env.example`)
