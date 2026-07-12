from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import FavoritesManager

logger = logging.getLogger(__name__)


class FavoriteExportService:
    """Service to export favorites in various formats."""

    def __init__(self, manager: FavoritesManager):
        self._manager = manager

    async def export_favorites(self, user_id: int) -> str | None:
        """Export favorites as JSON string. Returns None if no favorites."""
        try:
            result = await self._manager.get_favorites(user_id, limit=1000)
            items = result.get("items", [])
            if not items:
                return None
            return json.dumps(items, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"导出收藏失败: {e}")
            return None
