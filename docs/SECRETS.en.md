**Language:** [한국어](SECRETS.md) | **English**

# GitHub Secrets

To run Macro Pulse Bot correctly through GitHub Actions, add the following repository secrets.

The workflows run inside a runtime image built from `uv.lock`.

Path:
`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

## Delivery Platforms

### Telegram

- `TELEGRAM_BOT_TOKEN`: the token from BotFather for your Telegram bot
- `TELEGRAM_CHAT_ID`: the chat or channel ID that should receive the report

### Discord

- `DISCORD_WEBHOOK_URL`: the Incoming Webhook URL for the Discord channel that should receive the report

## Notes

- Secret names must match exactly.
- Delivery platforms without configured secrets are skipped.

## Optional

### Web Report Link

- `PAGES_REPORT_URL`: the GitHub Pages report URL appended to the Telegram/Discord summary
- Because this is a public URL, prefer adding it as a repository variable under `Settings > Secrets and variables > Actions > Variables`.
- Example: `https://your-github-username.github.io/your-repository/`
