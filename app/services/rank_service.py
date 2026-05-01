from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..cache import TTLCache

_FETCH_TIMEOUT_MS = 25000
_OVERALL_TIMEOUT_S = 30


class RankService:

    def __init__(self, rank_cache: "TTLCache", refresh_interval: int = 600):
        self.rank_cache = rank_cache
        self.refresh_interval = refresh_interval
        self._refresh_task: Optional[asyncio.Task] = None
        self._warming = False

    async def start_background_refresh(self) -> None:
        if self._refresh_task is not None:
            return
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logging.info("排行榜后台刷新已启动，间隔: %ds", self.refresh_interval)

    async def stop_background_refresh(self) -> None:
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
            logging.info("排行榜后台刷新已停止")

    async def _refresh_loop(self) -> None:
        await self._warm_cache()
        while True:
            try:
                await asyncio.sleep(self.refresh_interval)
                await self._warm_cache()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error("排行榜后台刷新异常: %s", e, exc_info=True)
                await asyncio.sleep(60)

    async def _warm_cache(self) -> None:
        if self._warming:
            return
        self._warming = True
        try:
            for page in range(1, 4):
                cache_key = ("rank", 20, page)
                if self.rank_cache.get(cache_key) is not None:
                    continue
                try:
                    result = await self._try_javdb_rankings(20, page)
                    if result:
                        logging.info("排行榜预热成功: page=%d, %d 个演员", page, len(result))
                    else:
                        logging.warning("排行榜预热返回空: page=%d", page)
                except Exception as e:
                    logging.error("排行榜预热失败: page=%d, %s", page, e, exc_info=True)
        finally:
            self._warming = False

    async def get_hot_star_rankings(self, limit: int = 20, page: int = 1) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 50))
        page = max(1, min(page, 5))
        cache_key = ("rank", limit, page)
        cached = self.rank_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await asyncio.wait_for(
                self._try_javdb_rankings(limit, page),
                timeout=_OVERALL_TIMEOUT_S,
            )
            if result is not None:
                return result
        except asyncio.TimeoutError:
            logging.warning("排行榜获取超时(%ds)，返回缓存", _OVERALL_TIMEOUT_S)

        fallback = self.rank_cache.get(("rank", limit, 1))
        return fallback or []

    async def _try_javdb_rankings(
        self, limit: int, page: int, timeout: int = _FETCH_TIMEOUT_MS
    ) -> List[Dict[str, Any]] | None:
        try:
            from ..browser_pool import get_actors_from_javdb

            logging.info("获取 JavDb 排行榜: page=%d, limit=%d", page, limit)
            actors = await get_actors_from_javdb(limit=limit, page=page, timeout=timeout)
            if actors:
                cache_key = ("rank", limit, page)
                self.rank_cache.set(cache_key, actors)
                logging.info("JavDb 排行榜获取成功: %d 个演员", len(actors))
                return actors
            logging.warning("JavDb 排行榜返回空结果")
        except Exception as e:
            logging.error("获取 JavDb 排行榜失败: %s", e, exc_info=True)

        return None
