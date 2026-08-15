"""run_magnet_reply: AV-ID searches get recorded to history."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers.magnet import run_magnet_reply


@pytest.fixture(autouse=True)
def _setup(shared_global, monkeypatch):
    import app.fav as fav_mod
    self_fav_mgr = AsyncMock()
    self_fav_mgr.increment_stat = AsyncMock()
    self_fav_mgr.record_favorite_query = AsyncMock(return_value=True)
    monkeypatch.setattr(
        fav_mod, "get_favorites_manager", AsyncMock(return_value=self_fav_mgr)
    )
    # run_magnet_reply calls these via asyncio.to_thread → keep them sync mocks
    # returning plain values (an AsyncMock would leak an un-awaited coroutine).
    svc = shared_global.service
    svc.get_av_meta = MagicMock(return_value=None)
    svc.get_av_magnets = MagicMock(return_value=[])
    shared_global.config.magnet_timeout = 5
    shared_global.config.magnet_limit = 5
    return self_fav_mgr


@pytest.mark.asyncio
async def test_records_query_with_user_id(mock_msg, _setup):
    await run_magnet_reply(mock_msg, "SSIS-123", user_id=12345)
    _setup.record_favorite_query.assert_awaited_once_with(12345, "SSIS-123")


@pytest.mark.asyncio
async def test_no_record_without_user_id(mock_msg, _setup):
    await run_magnet_reply(mock_msg, "SSIS-123")
    _setup.record_favorite_query.assert_not_called()
