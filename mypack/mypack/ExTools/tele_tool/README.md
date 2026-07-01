# tele_tool

What it does: sends a text message or a file (photo/video/audio/document) to a
Telegram chat via the Telegram Bot API.

Requires:
  - pip: httpx
Env:
  - TELEGRAM_BOT_TOKEN   (create a bot with @BotFather)
  - TELEGRAM_CHAT_ID     (your chat id, e.g. from @userinfobot)

Set the env vars in `ExAgents/tele_agent/.env` (the agent that owns this tool loads
that file at startup). See `ExTools/tele_tool/.env.example` for the keys.
