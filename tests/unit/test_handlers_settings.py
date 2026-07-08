"""Tests for settings handler: language_cmd, language_callback."""
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestLanguageCmd:
    """language_cmd: display, switch language."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        from app.handlers.settings import language_cmd
        self._handler = language_cmd
        import app.handlers.settings as settings_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_user_language.return_value = "zh_CN"
        self._fav_mgr.set_user_language = AsyncMock()
        monkeypatch.setattr(settings_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))
        # Make is_supported work correctly for tests
        shared_global.service.i18n.is_supported.side_effect = lambda lang: lang in ("zh_CN", "en_US", "ja_JP")

    async def _call(self, update, context):
        """Call decorated handler (Telegram-style: update, context only)."""
        await self._handler(update, context)

    async def test_no_args_shows_current(self, mock_update, mock_context):
        """No args → show current language."""
        mock_context.args = []
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once()

    async def test_switch_to_english(self, mock_update, mock_context):
        """Switch to en_US → set language."""
        mock_context.args = ["en_US"]
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        self._fav_mgr.set_user_language.assert_awaited_once()

    async def test_switch_to_japanese(self, mock_update, mock_context):
        """Switch to ja_JP → set language."""
        mock_context.args = ["ja_JP"]
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        self._fav_mgr.set_user_language.assert_awaited_once()

    async def test_invalid_language(self, mock_update, mock_context):
        """Invalid language code → show error."""
        mock_context.args = ["fr_FR"]
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once()
        self._fav_mgr.set_user_language.assert_not_called()


class TestLanguageCallback:
    """language_callback: inline keyboard language switching."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        import app.handlers.settings as settings_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.set_user_language = AsyncMock()
        monkeypatch.setattr(settings_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))
        # Make is_supported work correctly for tests
        shared_global.service.i18n.is_supported.side_effect = lambda lang: lang in ("zh_CN", "en_US", "ja_JP")

    @pytest.mark.asyncio
    async def test_switch_to_english(self, mock_update, mock_context, mock_q):
        """lang:en_US → set language."""
        from app.handlers.settings import language_callback
        mock_q.data = "lang:en_US"
        mock_update.callback_query = mock_q
        from app.handlers import _get_shared
        shared = _get_shared()
        shared.config.allowed_user_ids = {12345}
        await language_callback(mock_update, mock_context)
        self._fav_mgr.set_user_language.assert_awaited_once_with(12345, "en_US")

    @pytest.mark.asyncio
    async def test_switch_to_japanese(self, mock_update, mock_context, mock_q):
        """lang:ja_JP → set language."""
        from app.handlers.settings import language_callback
        mock_q.data = "lang:ja_JP"
        mock_update.callback_query = mock_q
        from app.handlers import _get_shared
        shared = _get_shared()
        shared.config.allowed_user_ids = {12345}
        await language_callback(mock_update, mock_context)
        self._fav_mgr.set_user_language.assert_awaited_once_with(12345, "ja_JP")

    @pytest.mark.asyncio
    async def test_auth_required(self, mock_update, mock_context, mock_q):
        """Unauthorized → show alert."""
        from app.handlers.settings import language_callback
        mock_q.data = "lang:en_US"
        mock_update.callback_query = mock_q
        from app.handlers import _get_shared
        shared = _get_shared()
        shared.config.allowed_user_ids = {99999}
        mock_update.effective_user.id = 12345
        await language_callback(mock_update, mock_context)
        mock_q.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_lang_ignored(self, mock_update, mock_context, mock_q):
        """Invalid lang code → ignored, no set."""
        from app.handlers.settings import language_callback
        mock_q.data = "lang:invalid"
        mock_update.callback_query = mock_q
        from app.handlers import _get_shared
        shared = _get_shared()
        shared.config.allowed_user_ids = {12345}
        await language_callback(mock_update, mock_context)
        self._fav_mgr.set_user_language.assert_not_called()