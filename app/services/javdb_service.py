from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from jvav import JavDbUtil
    from ..cache import TTLCache
    from ..rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class JavDbService:
    """JavDb AV 元数据子服务。

    JavDb API 被 Cloudflare 拦截，最新作品查询走 jvav 库 API。
    降级策略：JavDb 失败 → 空列表（由调用方回退到 JavBus）
    """

    def __init__(
        self,
        javdb_util: "JavDbUtil",
        av_meta_cache: "TTLCache",
        javdb_limiter: "RateLimiter",
        uncensored: bool = False,
    ):
        self.javdb = javdb_util
        self.av_meta_cache = av_meta_cache
        self._javdb_limiter = javdb_limiter
        self.uncensored = uncensored

    def get_av_meta(self, av_id: str) -> Dict[str, Any]:
        """获取单个 AV 的元数据（兼容 JavBus 格式）。"""
        cached = self.av_meta_cache.get(("javdb", av_id))
        if cached is not None:
            return cached

        meta: Dict[str, Any] = {
            "id": av_id,
            "date": "未知",
            "img": "",
            "url": "",
            "title": "",
        }
        try:
            self._javdb_limiter.wait()
            code, av = self.javdb.get_av_by_id(
                av_id, is_nice=False, is_uncensored=self.uncensored
            )
            if code == 200 and isinstance(av, dict):
                date = (av.get("date") or "").strip()
                img = (av.get("img") or "").strip()
                url = (av.get("url") or "").strip()
                title = (av.get("title") or "").strip()
                if date:
                    meta["date"] = date
                if img.startswith("http://") or img.startswith("https://"):
                    meta["img"] = img
                if url:
                    meta["url"] = url
                if title:
                    meta["title"] = title
        except Exception:
            logger.debug("获取JavDb AV元数据失败: av_id=%s", av_id, exc_info=True)

        self.av_meta_cache.set(("javdb", av_id), meta)
        return meta

    async def build_latest_works_async(self, ids: List[str]) -> List[Dict[str, Any]]:
        """批量获取作品元数据（异步版本）。"""
        if not ids:
            return []

        async def _fetch(idx: int, av_id: str) -> Dict[str, Any]:
            try:
                return await asyncio.to_thread(self.get_av_meta, av_id)
            except Exception:
                logger.debug("获取JavDb作品元数据失败: av_id=%s", av_id, exc_info=True)
                return {"id": av_id, "date": "未知", "img": "", "url": "", "title": ""}

        tasks = [asyncio.create_task(_fetch(idx, av_id)) for idx, av_id in enumerate(ids)]
        results = await asyncio.gather(*tasks)
        return list(results)

    # get_latest_works removed — JavDb endpoint disabled due to Cloudflare.
    # All latest-works queries go through JavBus via ActressService.
