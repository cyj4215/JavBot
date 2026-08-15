"""Digest push mode: settings, queue accumulation, digest message sending."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.fav import FavoritesManager
from app.models import MergedWork
from tests.unit.test_favorites import _mock_pool_acquire


@pytest.fixture
def manager():
    pool = MagicMock()
    pool.acquire = _mock_pool_acquire(MagicMock())
    return FavoritesManager(pool)


@pytest.mark.asyncio
async def test_set_push_mode_digest(manager):
    manager._execute = AsyncMock(return_value=1)
    assert await manager.set_push_mode(123, "digest") is True
    sql = manager._execute.call_args[0][0]
    assert "push_mode" in sql


@pytest.mark.asyncio
async def test_set_push_mode_invalid(manager):
    manager._execute = AsyncMock(return_value=1)
    assert await manager.set_push_mode(123, "bogus") is False
    manager._execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_push_settings_returns_mode(manager):
    manager._select_one = AsyncMock(return_value={"push_enabled": 1, "push_mode": "digest", "last_check": None})
    settings = await manager.get_push_settings(123)
    assert settings["push_mode"] == "digest"


class TestDigestAccumulation:
    """check_and_push_new_works 对 digest 用户只入队不发送。"""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        import app.handlers.push as push_mod
        from app.models import ActressProfile
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_users_with_push_enabled.return_value = [12345]
        self._fav_mgr.get_push_settings.return_value = {
            "push_enabled": True, "push_mode": "digest", "last_check": None,
        }
        self._fav_mgr.get_favorites.return_value = {
            "items": [{"actress_name": "TestActress"}], "next_cursor": None, "total": 1,
        }
        self._fav_mgr.record_user_work.return_value = True
        self._fav_mgr.update_last_check = AsyncMock()
        monkeypatch.setattr(
            push_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr)
        )
        shared_global.service.query_profile_async.return_value = ActressProfile(
            found=True, query="TestActress", star_name="TestActress", star_id="T-1",
            latest_works=[MergedWork(id="DIGEST-001", img="", date="2026-08-15", title="Digest Work")],
        )
        shared_global.config.push_enabled_global = True
        shared_global.config.allowed_user_ids = {12345}
        shared_global.config.push_batch_delay = 0
        push_mod._digest_queue.clear()

    @pytest.mark.asyncio
    async def test_digest_user_queues_not_sends(self, shared_global, monkeypatch):
        from app.handlers.push import _digest_queue, check_and_push_new_works
        mocked_send = AsyncMock()
        monkeypatch.setattr(
            "app.handlers.push.send_new_work_notification", mocked_send
        )
        context = MagicMock()
        context.bot = AsyncMock()
        await check_and_push_new_works(context)
        mocked_send.assert_not_called()
        assert len(_digest_queue.get(12345, [])) == 1
        self._fav_mgr.record_user_work.assert_awaited_once()


class TestSendDigestMessage:
    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        monkeypatch.setattr("app.improved_utils.download_image", lambda *a, **kw: None)

    @pytest.mark.asyncio
    async def test_sends_one_message_with_grouped_works(self):
        from app.handlers.push import send_digest_message
        bot = AsyncMock()
        items = [
            {"actress_name": "A", "work": MergedWork(id="A-001", img="", date="2026-08-15", title="T1")},
            {"actress_name": "A", "work": MergedWork(id="A-002", img="", date="2026-08-15", title="T2")},
            {"actress_name": "B", "work": MergedWork(id="B-001", img="", date="2026-08-15", title="T3")},
        ]
        await send_digest_message(bot, 12345, items)
        # img_url 为空 → send_photo_with_fallback 走 _send_text → bot.send_message
        bot.send_message.assert_awaited_once()
        text = bot.send_message.call_args.kwargs["text"]
        assert "A-001" in text
        assert "A-002" in text
        assert "B-001" in text
