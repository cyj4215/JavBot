"""Tests for push handler: push_toggle_cmd, check_and_push_new_works."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers.push import (
    check_and_push_new_works,
    send_new_work_notification,
)
from app.models import FavoriteEntry, MergedWork


class TestPushToggleCmd:
    """push_toggle_cmd: on/off toggle, status display."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        from app.handlers.push import push_toggle_cmd
        self._handler = push_toggle_cmd
        import app.handlers.push as push_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_push_settings.return_value = {
            "push_enabled": True, "push_mode": "instant", "last_check": None,
        }
        self._fav_mgr.set_push_mode = AsyncMock()
        monkeypatch.setattr(push_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))

    async def _call(self, update, context):
        """Call the decorated handler (Telegram-style: update, context only)."""
        await self._handler(update, context)

    async def test_show_status_when_no_args(self, mock_update, mock_context):
        """No args → show current push status."""
        mock_context.args = []
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once()
        text = mock_update.effective_message.reply_text.call_args[0][0]
        assert "开启" in text or "推送" in text

    async def test_enable_push(self, mock_update, mock_context):
        """push on → enable push."""
        mock_context.args = ["on"]
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        self._fav_mgr.set_push_mode.assert_awaited_once_with(12345, "instant")

    async def test_disable_push(self, mock_update, mock_context):
        """push off → disable push."""
        mock_context.args = ["off"]
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        self._fav_mgr.set_push_mode.assert_awaited_once_with(12345, "off")

    async def test_invalid_arg_shows_usage(self, mock_update, mock_context):
        """Invalid arg → show usage."""
        mock_context.args = ["invalid"]
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once()

    async def test_push_off_with_disable_alias(self, mock_update, mock_context):
        """push disable → disable push."""
        mock_context.args = ["disable"]
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        self._fav_mgr.set_push_mode.assert_awaited_once_with(12345, "off")


class TestCheckAndPushNewWorks:
    """check_and_push_new_works: global push flag, user list, work discovery."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        import app.handlers.push as push_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_users_with_push_enabled.return_value = [12345]
        self._fav_mgr.get_push_settings.return_value = {
            "push_enabled": True, "push_mode": "instant", "last_check": None,
        }
        self._fav_mgr.get_favorites.return_value = {"items": [
            {"actress_name": "TestActress", "actress_id": "TA-001", "created_at": "2026-05-01"},
        ], "next_cursor": None, "total": 1}
        self._fav_mgr.record_user_work.return_value = True
        self._fav_mgr.update_last_check = AsyncMock()
        monkeypatch.setattr(push_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))
        self._svc = shared_global.service
        self._svc.query_profile_async.return_value = _fake_profile(
            found=True, star_name="TestActress",
            latest_works=[MergedWork(id="NEW-001", img="", date="2026-07-01", title="New Work")],
        )
        shared_global.config.push_enabled_global = True
        shared_global.config.allowed_user_ids = {12345}

    @pytest.mark.asyncio
    async def test_push_global_disabled_skips(self, shared_global):
        """push_enabled_global=False → skip check."""
        shared_global.config.push_enabled_global = False
        context = MagicMock()
        await check_and_push_new_works(context)
        # No favorites query = skipped
        self._fav_mgr.get_users_with_push_enabled.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_users_with_push(self, shared_global):
        """No users with push enabled → skip."""
        self._fav_mgr.get_users_with_push_enabled.return_value = []
        context = MagicMock()
        await check_and_push_new_works(context)
        self._fav_mgr.get_favorites.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_work_discovered(self, shared_global):
        """New work found → notification sent."""
        context = MagicMock()
        context.bot = AsyncMock()
        await check_and_push_new_works(context)
        # record_user_work called for the new work
        self._fav_mgr.record_user_work.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_new_work_duplicate(self, shared_global):
        """Work already recorded → no notification."""
        self._fav_mgr.record_user_work.return_value = False
        context = MagicMock()
        context.bot = AsyncMock()
        await check_and_push_new_works(context)
        # record_user_work called but returned False (already recorded)
        self._fav_mgr.record_user_work.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_service_exception_handled(self, shared_global):
        """Service exception → skip that actress, don't crash."""
        self._svc.query_profile_async.side_effect = Exception("network error")
        context = MagicMock()
        context.bot = AsyncMock()
        # Should not raise
        await check_and_push_new_works(context)

    @pytest.mark.asyncio
    async def test_skips_user_not_in_whitelist(self, shared_global):
        """User not in allowed_user_ids → skip."""
        shared_global.config.allowed_user_ids = {99999}
        self._fav_mgr.get_users_with_push_enabled.return_value = [12345]
        context = MagicMock()
        context.bot = AsyncMock()
        await check_and_push_new_works(context)
        # get_favorites should not be called for this user
        self._fav_mgr.get_favorites.assert_not_called()


class TestSendNewWorkNotification:
    """send_new_work_notification: message formatting, error handling."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        self._shared = shared_global
        # Prevent actual HTTP requests in image download
        monkeypatch.setattr("app.improved_utils.download_image", lambda *a, **kw: None)

    @pytest.mark.asyncio
    async def test_sends_notification_with_work_data(self):
        """Notification sent with correct work data."""
        bot = AsyncMock()
        work = MergedWork(id="TEST-001", img="", date="2026-07-01", title="Test Title")
        await send_new_work_notification(bot, 12345, "TestActress", work)
        bot.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_missing_work_fields(self):
        """Missing fields → no crash."""
        bot = AsyncMock()
        work = MergedWork(id="TEST-001")
        await send_new_work_notification(bot, 12345, "TestActress", work)
        bot.send_message.assert_awaited_once()


# ── Helpers ──

def _fake_profile(found=True, star_name="Test", query="Test", latest_works=None):
    from app.models import ActressProfile
    return ActressProfile(
        found=found, query=query, star_name=star_name,
        star_id=star_name.upper() if found else "",
        latest_works=latest_works or [],
        extra_info=None,
        avatar_url="",
    )
