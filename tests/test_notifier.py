import os
import sys
import unittest
from unittest.mock import AsyncMock, patch


sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from macro_pulse.delivery.notifier import send_discord_report, send_telegram_report


class FakeHttpResponse:
    status = 204

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class NotifierTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_telegram_report_sends_message_and_images(self):
        with (
            patch("macro_pulse.delivery.notifier.Bot") as bot_cls,
            patch("macro_pulse.delivery.notifier.os.path.exists", return_value=True),
            patch("builtins.open", unittest.mock.mock_open(read_data=b"image")),
        ):
            bot = AsyncMock()
            bot_cls.return_value = bot

            result = await send_telegram_report(
                "token",
                "chat-id",
                "hello",
                image_paths=["sample.png"],
                attempts=1,
            )

        self.assertTrue(result)
        bot.send_message.assert_awaited_once_with(chat_id="chat-id", text="hello")
        bot.send_photo.assert_awaited_once()

    async def test_send_discord_report_posts_message_and_images(self):
        with (
            patch(
                "macro_pulse.delivery.notifier.urlopen",
                return_value=FakeHttpResponse(),
            ) as urlopen,
            patch("macro_pulse.delivery.notifier.os.path.exists", return_value=True),
            patch("builtins.open", unittest.mock.mock_open(read_data=b"image")),
        ):
            result = await send_discord_report(
                "https://discord.example/webhook",
                "hello",
                image_paths=["sample.png"],
                attempts=1,
            )

        self.assertTrue(result)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://discord.example/webhook")
        self.assertIn("multipart/form-data", request.get_header("Content-type"))
        self.assertIn(b'"content": "hello"', request.data)
        self.assertIn(b'name="files[0]"; filename="sample.png"', request.data)

    async def test_send_discord_report_splits_long_messages(self):
        with patch(
            "macro_pulse.delivery.notifier.urlopen",
            return_value=FakeHttpResponse(),
        ) as urlopen:
            result = await send_discord_report(
                "https://discord.example/webhook",
                "x" * 2001,
                attempts=1,
            )

        self.assertTrue(result)
        self.assertEqual(urlopen.call_count, 2)
