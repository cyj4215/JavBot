"""Tests for search handler: cancel_search_callback."""
from unittest.mock import AsyncMock

import pytest

from app.handlers.search import run_search_reply
from app.models import ActressProfile


class TestCancelSearchCallback:
    """cancel_search_callback: verify user auth, cancel logic, edge cases."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global):
        from app.handlers.search import cancel_search_callback
        self._handler = cancel_search_callback

    async def _call(self, update, context):
        await self._handler(update, context)

    async def test_cancel_own_search(self, mock_update, mock_context, mock_q):
        """Cancel own pending search → answer with '已取消'."""
        from app.handlers.search import _pending_queries
        task = _add_dummy_pending_task(12345)
        mock_q.data = _signed_cancel("12345")
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once()
        assert 12345 not in _pending_queries
        _pending_queries.pop(12345, None)  # cleanup

    async def test_cancel_no_pending_task(self, mock_update, mock_context, mock_q):
        """No pending query → answer '没有正在进行的查询'."""
        mock_q.data = _signed_cancel("12345")
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once_with("没有正在进行的查询")

    async def test_cancel_other_user_denied(self, mock_update, mock_context, mock_q):
        """User tries to cancel another user's query → denied."""
        from app.handlers.search import _pending_queries
        task = _add_dummy_pending_task(99999)
        mock_q.data = _signed_cancel("99999")
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once_with("无权取消他人的查询", show_alert=True)
        _pending_queries.pop(99999, None)

    async def test_expired_token(self, mock_update, mock_context, mock_q):
        """Expired HMAC token → show alert."""
        mock_q.data = "cancel:bad"
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once_with("该操作已过期", show_alert=True)


# ── Helpers ──

def _signed_cancel(uid: str) -> str:
    from app.secure_callback import short_callback
    return short_callback("cancel", uid)


def _add_dummy_pending_task(uid: int):
    """Add a dummy completed task to _pending_queries for cancel tests."""
    import asyncio
    from app.handlers.search import _pending_queries
    task = asyncio.get_event_loop().create_future()
    task.cancel()
    _pending_queries[uid] = task
    return task


class TestRunSearchReplyRecordsHistory:
    """run_search_reply 成功后记录搜索历史。"""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        import app.handlers.search as search_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_user_language.return_value = "zh_CN"
        self._fav_mgr.is_favorite = AsyncMock(return_value=False)
        self._fav_mgr.record_favorite_query = AsyncMock(return_value=True)
        self._fav_mgr.increment_stat = AsyncMock()
        monkeypatch.setattr(
            search_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr)
        )
        self._svc = shared_global.service
        self._svc.query_profile_async.return_value = ActressProfile(
            found=True, query="三上悠亜", star_name="三上悠亜", star_id="X"
        )
        shared_global.config.send_latest_covers = False

    @pytest.mark.asyncio
    async def test_records_query_after_success(self, mock_msg):
        from app.handlers.search import run_search_reply
        await run_search_reply(mock_msg, "三上悠亜", user_id=12345)
        self._fav_mgr.record_favorite_query.assert_awaited_once_with(12345, "三上悠亜")
