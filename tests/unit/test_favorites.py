"""Unit tests for FavoritesManager (async MySQL).

Patches internal query methods to avoid real DB.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.fav_manager import FavoritesManager


def _mock_pool_acquire(conn_mock):
    """Return a callable for pool.acquire that returns an async CM yielding conn."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn_mock)
    cm.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=cm)


def _mock_conn(**kwargs):
    """Create a mock connection with cursor."""
    conn = MagicMock()
    cursor = AsyncMock()
    for k, v in kwargs.items():
        setattr(cursor, k, v)
    conn.cursor.return_value.__aenter__.return_value = cursor
    conn.commit = AsyncMock()
    return conn


@pytest.fixture
def manager():
    """FavoritesManager with fully mocked pool (no real DB)."""
    pool = MagicMock()
    pool.acquire = _mock_pool_acquire(MagicMock())
    return FavoritesManager(pool)


@pytest.mark.asyncio
async def test_is_favorite_exists(manager):
    manager._select_one = AsyncMock(return_value={"val": 1})
    assert await manager.is_favorite(123, "三上悠亜") is True


@pytest.mark.asyncio
async def test_is_favorite_not_found(manager):
    manager._select_one = AsyncMock(return_value=None)
    assert await manager.is_favorite(123, "Unknown") is False


@pytest.mark.asyncio
async def test_get_favorites_empty(manager):
    manager._select_one = AsyncMock(return_value={"cnt": 0})
    manager._select_all = AsyncMock(return_value=[])
    result = await manager.get_favorites(123)
    assert result["items"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_get_favorites_with_data(manager):
    manager._select_one = AsyncMock(return_value={"cnt": 1})
    manager._select_all = AsyncMock(return_value=[
        {"id": 1, "actress_name": "河北彩花", "actress_id": "ABC123",
         "actress_data": None, "created_at": "2024-01-01 00:00:00"}
    ])
    result = await manager.get_favorites(123)
    assert len(result["items"]) == 1
    assert result["items"][0]["actress_name"] == "河北彩花"
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_add_favorite(manager):
    manager.sync_user = AsyncMock(return_value=True)
    conn = _mock_conn(execute=AsyncMock(return_value=0))
    manager._pool.acquire = _mock_pool_acquire(conn)
    result = await manager.add_favorite(123, "河北彩花", "ABC123")
    assert result is True


@pytest.mark.asyncio
async def test_remove_favorite_found(manager):
    manager._execute = AsyncMock(return_value=1)
    assert await manager.remove_favorite(123, "河北彩花") is True


@pytest.mark.asyncio
async def test_remove_favorite_not_found(manager):
    manager._execute = AsyncMock(return_value=0)
    assert await manager.remove_favorite(123, "Nonexistent") is False


@pytest.mark.asyncio
async def test_get_favorite_count(manager):
    manager._select_one = AsyncMock(return_value={"cnt": 5})
    assert await manager.get_favorite_count(123) == 5


@pytest.mark.asyncio
async def test_get_favorite_count_zero(manager):
    manager._select_one = AsyncMock(return_value=None)
    assert await manager.get_favorite_count(123) == 0


@pytest.mark.asyncio
async def test_record_work_new(manager):
    conn = _mock_conn(rowcount=1)
    manager._pool.acquire = _mock_pool_acquire(conn)
    assert await manager.record_actress_work("河北彩花", "SSIS-123", "Title") is True


@pytest.mark.asyncio
async def test_record_work_duplicate(manager):
    conn = _mock_conn(rowcount=0)
    manager._pool.acquire = _mock_pool_acquire(conn)
    assert await manager.record_actress_work("河北彩花", "SSIS-123") is False


@pytest.mark.asyncio
async def test_cleanup_old_data(manager):
    conn = _mock_conn(rowcount=5)
    manager._pool.acquire = _mock_pool_acquire(conn)
    await manager.cleanup_old_data(days=90)
    assert conn.cursor.return_value.__aenter__.return_value.execute.await_count >= 2
    conn.commit.assert_awaited_once()
