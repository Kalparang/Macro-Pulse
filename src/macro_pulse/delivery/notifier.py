import json
import mimetypes
import os
import uuid
from asyncio import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from telegram import Bot

from ..core.logging import get_logger


logger = get_logger(__name__)

DISCORD_CONTENT_LIMIT = 2000


async def send_telegram_report(
    token,
    chat_id,
    message_text="Daily Macro Pulse Report",
    image_path=None,
    image_paths=None,
    attempts=2,
):
    if not token or not chat_id:
        logger.info("Telegram token or chat_id missing. Skipping Telegram.")
        return False

    photo_paths = list(image_paths or [])
    if image_path and not photo_paths:
        photo_paths.append(image_path)

    for attempt in range(1, attempts + 1):
        try:
            bot = Bot(token=token)
            await bot.send_message(chat_id=chat_id, text=message_text)

            for photo_path in photo_paths:
                if photo_path and os.path.exists(photo_path):
                    with open(photo_path, "rb") as image_handle:
                        await bot.send_photo(chat_id=chat_id, photo=image_handle)
                    logger.info("Telegram photo sent: %s", photo_path)

            return True
        except Exception as exc:
            logger.warning(
                "Failed to send Telegram message (attempt %s/%s): %s",
                attempt,
                attempts,
                exc,
            )
            if attempt == attempts:
                logger.exception("Telegram delivery failed after retries")
                return False
            await sleep(1)


async def send_discord_report(
    webhook_url,
    message_text="Daily Macro Pulse Report",
    image_path=None,
    image_paths=None,
    attempts=2,
):
    if not webhook_url:
        logger.info("Discord webhook URL missing. Skipping Discord.")
        return False

    attachment_paths = _existing_attachment_paths(image_path, image_paths)
    content_chunks = _split_discord_content(message_text or "")
    if not content_chunks and not attachment_paths:
        logger.info("Discord message and attachments are empty. Skipping Discord.")
        return False

    for attempt in range(1, attempts + 1):
        try:
            if content_chunks:
                for index, content in enumerate(content_chunks):
                    is_last_chunk = index == len(content_chunks) - 1
                    _post_discord_webhook(
                        webhook_url,
                        content,
                        attachment_paths if is_last_chunk else [],
                    )
            else:
                _post_discord_webhook(webhook_url, "", attachment_paths)

            for attachment_path in attachment_paths:
                logger.info("Discord attachment sent: %s", attachment_path)
            return True
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            RuntimeError,
            ValueError,
        ) as exc:
            logger.warning(
                "Failed to send Discord message (attempt %s/%s): %s",
                attempt,
                attempts,
                exc,
            )
            if attempt == attempts:
                logger.exception("Discord delivery failed after retries")
                return False
            await sleep(1)


def _existing_attachment_paths(image_path=None, image_paths=None):
    attachment_paths = list(image_paths or [])
    if image_path and not attachment_paths:
        attachment_paths.append(image_path)
    return [path for path in attachment_paths if path and os.path.exists(path)]


def _split_discord_content(content: str) -> list[str]:
    if not content:
        return []

    chunks: list[str] = []
    current = ""
    for line in content.splitlines(keepends=True):
        if len(line) > DISCORD_CONTENT_LIMIT:
            if current:
                _append_discord_content_chunk(chunks, current)
                current = ""
            for index in range(0, len(line), DISCORD_CONTENT_LIMIT):
                _append_discord_content_chunk(
                    chunks,
                    line[index : index + DISCORD_CONTENT_LIMIT],
                )
            continue

        if len(current) + len(line) > DISCORD_CONTENT_LIMIT:
            _append_discord_content_chunk(chunks, current)
            current = line
        else:
            current += line

    if current:
        _append_discord_content_chunk(chunks, current)

    return chunks


def _append_discord_content_chunk(chunks: list[str], content: str) -> None:
    chunk = content.rstrip("\n")
    if chunk:
        chunks.append(chunk)


def _post_discord_webhook(webhook_url, content, attachment_paths):
    if attachment_paths:
        body, content_type = _build_discord_multipart_body(content, attachment_paths)
    else:
        body = json.dumps({"content": content}).encode("utf-8")
        content_type = "application/json"

    request = Request(
        webhook_url,
        data=body,
        headers={
            "Content-Type": content_type,
            "User-Agent": "Macro-Pulse Bot",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        status = getattr(response, "status", response.getcode())
        if status >= 300:
            raise RuntimeError(f"Discord webhook returned HTTP {status}")


def _build_discord_multipart_body(content, attachment_paths):
    boundary = f"macro-pulse-{uuid.uuid4().hex}"
    parts = []

    def append_field(name, value, *, filename=None, content_type=None):
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'

        headers = [f"--{boundary}", disposition]
        if content_type:
            headers.append(f"Content-Type: {content_type}")

        parts.append(("\r\n".join(headers) + "\r\n\r\n").encode("utf-8"))
        parts.append(value)
        parts.append(b"\r\n")

    append_field(
        "payload_json",
        json.dumps({"content": content}).encode("utf-8"),
        content_type="application/json",
    )

    for index, attachment_path in enumerate(attachment_paths):
        filename = os.path.basename(attachment_path)
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with open(attachment_path, "rb") as attachment_handle:
            append_field(
                f"files[{index}]",
                attachment_handle.read(),
                filename=filename,
                content_type=content_type,
            )

    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"
