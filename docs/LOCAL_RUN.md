**Language:** **한국어** | [English](LOCAL_RUN.en.md)

# 로컬 / Docker 실행 가이드

이 문서는 Macro Pulse Bot을 내 컴퓨터에서 직접 실행하는 방법을 정리한 문서입니다.

## 1. uv 실행

### 설치

```bash
uv python install
uv sync --all-groups
```

- 이 저장소는 [`pyproject.toml`](../pyproject.toml)과 [`uv.lock`](../uv.lock)을 기준으로 의존성을 관리합니다.
- 기본 Python 버전은 [`.python-version`](../.python-version) 파일에 맞춰집니다.

### `.env` 준비

프로젝트 루트에 `.env` 파일을 만들고 아래 값을 넣습니다.

```ini
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here
PAGES_REPORT_URL=https://your-github-username.github.io/your-repository/
```

- 텔레그램 값이 없으면 텔레그램 전송은 건너뜁니다.
- 디스코드 값이 없으면 디스코드 전송은 건너뜁니다.
- `PAGES_REPORT_URL`이 있으면 전송 요약 하단에 웹 리포트 링크를 붙입니다.

### 리포트만 생성

```bash
uv run python src/main.py --dry-run
```

실행 후 `macro_pulse_report.html` 파일이 만들어집니다.

### 실제 전송까지 실행

```bash
uv run python src/main.py
```

### 시장 모드 직접 선택

```bash
uv run python src/main.py --market KR
uv run python src/main.py --market US
```

- `KR`: 한국장 기준
- `US`: 미국장 기준
- 옵션을 빼면 UTC 시간을 기준으로 자동 선택합니다.

## 2. Docker 실행

### 이미지 빌드

```bash
docker build -t macro-pulse .
```

### Dry run 실행

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD:/app" \
  -w /app \
  macro-pulse \
  uv run --frozen python src/main.py --dry-run
```

### 실제 실행

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD:/app" \
  -w /app \
  macro-pulse \
  uv run --frozen python src/main.py
```

## 3. 결과 파일

- `macro_pulse_report.html`: 생성된 HTML 리포트
- 스크린샷 PNG: 전송용 임시 파일

## 4. 문제 해결

- 스크린샷이 실패하면 Chrome/Chromium 실행 환경을 확인하세요.
- 텔레그램이 오지 않으면 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 다시 확인하세요.
- 디스코드 메시지가 오지 않으면 `DISCORD_WEBHOOK_URL`을 다시 확인하세요.
- 일부 데이터가 비어 있으면 외부 데이터 소스 응답 문제일 수 있습니다.
