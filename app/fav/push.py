from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .manager import FavoritesManager

logger = logging.getLogger(__name__)


class PushService:
    """Push notification service wrapping FavoritesManager push methods."""

    def __init__(self, manager: FavoritesManager):
        self._manager = manager

    async def _select_one(self, query: str, params: tuple = ()) -> dict[str, Any] | None:
        return await self._manager._select_one(query, params)

    async def _select_all(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        return await self._manager._select_all(query, params)

    async def _execute(self, query: str, params: tuple = ()) -> int:
        return await self._manager._execute(query, params)

    async def get_push_settings(self, user_id: int) -> dict:
        try:
            row = await self._select_one(
                "SELECT * FROM user_push_settings WHERE user_id = %s",
                (user_id,),
            )
            if row:
                return {
                    "push_enabled": row["push_enabled"],
                    "last_check": str(row["last_check"]) if row.get("last_check") else None,
                }
            return {"push_enabled": 1, "last_check": None}
        except Exception as e:
            logger.error(f"获取推送设置失败: {e}")
            return {"push_enabled": 1, "last_check": None}

    async def set_push_enabled(self, user_id: int, enabled: bool) -> bool:
        try:
            await self._execute(
                """
                INSERT INTO user_push_settings (user_id, push_enabled, last_check)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    push_enabled = VALUES(push_enabled)
                """,
                (user_id, 1 if enabled else 0),
            )
            return True
        except Exception as e:
            logger.error(f"设置推送开关失败: {e}")
            return False

    async def update_last_check(self, user_id: int) -> bool:
        try:
            await self._execute(
                """
                INSERT INTO user_push_settings (user_id, push_enabled, last_check)
                VALUES (%s, 1, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    last_check = CURRENT_TIMESTAMP
                """,
                (user_id,),
            )
            return True
        except Exception as e:
            logger.error(f"更新检查时间失败: {e}")
            return False

    async def get_users_with_push_enabled(self) -> list[int]:
        try:
            rows = await self._select_all(
                """
                SELECT DISTINCT f.user_id
                FROM favorites f
                LEFT JOIN user_push_settings ups ON f.user_id = ups.user_id
                WHERE ups.user_id IS NULL OR ups.push_enabled = 1
                """,
            )
            return [r["user_id"] for r in rows]
        except Exception as e:
            logger.error(f"获取推送用户列表失败: {e}")
            return []
