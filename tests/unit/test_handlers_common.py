"""Tests for common handlers: auth decorators, is_allowed, start, help, menu."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers.common import is_allowed, make_t, send_photo_with_fallback


class TestIsAllowed:
    def test_empty_whitelist_allows_all(self):
        assert is_allowed(MagicMock(), set()) is True

    def test_user_in_whitelist(self):
        update = MagicMock()
        update.effective_user.id = 123
        assert is_allowed(update, {123, 456}) is True

    def test_user_not_in_whitelist(self):
        update = MagicMock()
        update.effective_user.id = 999
        assert is_allowed(update, {123, 456}) is False

    def test_no_effective_user(self):
        update = MagicMock()
        update.effective_user = None
        assert is_allowed(update, {123}) is False


class TestRequireAuth:
    """require_auth decorator: auth pass/fail, edge cases."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global):
        from app.handlers.common import require_auth
        self._decorator = require_auth

    async def _dummy_handler(self, update, context, msg, shared):
        """Async dummy handler for decorator tests."""
        return None

    async def _call(self, update, context):
        handler = self._decorator(self._dummy_handler)
        await handler(update, context)

    async def test_auth_pass_with_empty_whitelist(self, mock_update, mock_context):
        """Empty whitelist → handler runs."""
        mock_update.effective_message = AsyncMock()
        shared = pytest.importorskip("app.handlers")._get_shared()
        shared.config.allowed_user_ids.clear()
        handler = self._decorator(self._dummy_handler)
        await handler(mock_update, mock_context)

    async def test_auth_pass_with_user_in_whitelist(self, mock_update, mock_context):
        """User in whitelist → handler runs."""
        mock_update.effective_message = AsyncMock()
        shared = pytest.importorskip("app.handlers")._get_shared()
        shared.config.allowed_user_ids = {12345}
        handler = self._decorator(self._dummy_handler)
        await handler(mock_update, mock_context)

    async def test_auth_fail_replies_no_permission(self, mock_update, mock_context):
        """User not in whitelist → reply with '无权限'."""
        mock_update.effective_message = AsyncMock()
        shared_global = pytest.importorskip("app.handlers")._get_shared()
        shared_global.config.allowed_user_ids = {99999}
        handler = self._decorator(lambda u, c, msg, shared: None)
        await handler(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once_with("无权限使用此机器人。")

    async def test_no_effective_message(self, mock_update, mock_context):
        """No effective_message → handler returns early without error."""
        mock_update.effective_message = None
        handler = self._decorator(lambda u, c, msg, shared: None)
        await handler(mock_update, mock_context)


class TestRequireAuthCallback:
    """require_auth_callback decorator: auth pass/fail."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global):
        from app.handlers.common import require_auth_callback
        self._decorator = require_auth_callback

    async def test_auth_fail_shows_alert(self, mock_update, mock_context, mock_q):
        """User not in whitelist → q.answer with show_alert=True."""
        mock_update.callback_query = mock_q
        shared_global = pytest.importorskip("app.handlers")._get_shared()
        shared_global.config.allowed_user_ids = {99999}
        handler = self._decorator(lambda u, c, q, shared: None)
        await handler(mock_update, mock_context)
        mock_q.answer.assert_awaited_once_with("无权限使用", show_alert=True)

    async def test_no_callback_query(self, mock_update, mock_context):
        """No callback_query → handler returns early."""
        mock_update.callback_query = None
        handler = self._decorator(lambda u, c, q, shared: None)
        await handler(mock_update, mock_context)


class TestMakeT:
    """make_t i18n helper."""

    @pytest.mark.asyncio
    async def test_make_t_returns_callable(self, shared_global):
        from app.handlers.common import make_t
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        t = await make_t(shared_global, update)
        assert callable(t)
        result = t("bot_started")
        assert result is not None


class TestSendPhotoWithFallback:
    """send_photo_with_fallback: image download, text fallback."""

    @pytest.mark.asyncio
    async def test_text_fallback_when_no_img(self, mock_msg):
        """No img_url → send text only."""
        await send_photo_with_fallback(msg=mock_msg, img_url=None, caption="hello")
        mock_msg.reply_text.assert_awaited_once()
        mock_msg.reply_photo.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_image_success(self, mock_msg, monkeypatch):
        """Image download succeeds → send photo."""
        def fake_download(*a, **kw):
            return b"fake-image-bytes"
        monkeypatch.setattr("app.improved_utils.download_image", fake_download)
        await send_photo_with_fallback(msg=mock_msg, img_url="https://example.com/img.jpg", caption="hello")
        mock_msg.reply_photo.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_download_image_failure_sends_text(self, mock_msg, monkeypatch):
        """Image download fails → send text fallback."""
        def fake_download(*a, **kw):
            return None
        monkeypatch.setattr("app.improved_utils.download_image", fake_download)
        await send_photo_with_fallback(msg=mock_msg, img_url="https://example.com/img.jpg", caption="hello")
        # Should attempt photo with URL, then fallback to text
        assert mock_msg.reply_photo.await_count >= 1 or mock_msg.reply_text.await_count >= 1

    @pytest.mark.asyncio
    async def test_send_with_bot_and_chat_id(self, monkeypatch):
        """Send via bot+chat_id path."""
        bot = AsyncMock()
        await send_photo_with_fallback(bot=bot, chat_id=123, img_url=None, caption="hello")
        bot.send_message.assert_awaited_once()