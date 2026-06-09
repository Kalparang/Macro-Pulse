**Language:** **한국어** | [English](SECRETS.en.md)

# GitHub Secrets

GitHub Actions에서 Macro Pulse Bot을 정상적으로 실행하려면 저장소에 아래 Secret 값을 등록해야 합니다.

워크플로는 `uv.lock`을 기준으로 빌드된 런타임 이미지를 사용합니다.

경로:
`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

## 전송 플랫폼

### Telegram

- `TELEGRAM_BOT_TOKEN`: BotFather로 만든 텔레그램 봇의 토큰
- `TELEGRAM_CHAT_ID`: 리포트를 받을 채팅방 또는 채널의 ID

### Discord

- `DISCORD_WEBHOOK_URL`: 리포트를 받을 디스코드 채널의 Incoming Webhook URL

## 주의 사항

- Secret 이름은 위와 정확히 같아야 합니다.
- 설정하지 않은 전송 플랫폼은 건너뜁니다.
