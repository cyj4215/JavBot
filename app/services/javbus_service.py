from __future__ import annotations

import atexit
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from jvav import JavBusUtil
    from ..cache import TTLCache
    from ..rate_limiter import RateLimiter


class JavBusService:
    """JavBus AV 元数据与磁力链接子服务。"""

    def __init__(
        self,
        javbus_util: "JavBusUtil",
        av_meta_cache: "TTLCache",
        javbus_limiter: "RateLimiter",
        uncensored: bool = False,
        magnet_search_module=None,
    ):
        self.javbus = javbus_util
        self.av_meta_cache = av_meta_cache
        self._javbus_limiter = javbus_limiter
        self.uncensored = uncensored
        self._magnet_search = magnet_search_module
        self._executor = ThreadPoolExecutor(max_workers=6)
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        self._executor.shutdown(wait=False)

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def get_av_meta(
        self, av_id: str, is_uncensored: Optional[bool] = None
    ) -> Dict[str, Any]:
        if is_uncensored is None:
            is_uncensored = self.uncensored
        cached = self.av_meta_cache.get((av_id, is_uncensored))
        if cached is not None:
            return cached
        meta: Dict[str, Any] = {
            "id": av_id,
            "date": "未知",
            "img": "",
            "url": "",
            "title": "",
            "magnets": []
        }
        try:
            self._javbus_limiter.wait()
            code, av = self.javbus.get_av_by_id(av_id, is_nice=False, is_uncensored=is_uncensored)
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
                code, magnets = self.javbus.get_av_magnets(av_id, is_uncensored=is_uncensored)
                if code == 200 and magnets:
                    meta["magnets"] = [{"title": m.get("title", ""), "size": m.get("size", ""), "magnet": m.get("magnet", "")} for m in magnets[:3]]
            self.av_meta_cache.set((av_id, is_uncensored), meta)
        except Exception:
            logging.getLogger(__name__).debug("获取AV元数据失败: av_id=%s", av_id, exc_info=True)
        return meta

    def build_latest_works(self, ids: List[str]) -> List[Dict[str, Any]]:
        works: List[Dict[str, Any]] = [{} for _ in ids]
        if not ids:
            return works
        future_map = {
            self._executor.submit(self.get_av_meta, av_id): idx
            for idx, av_id in enumerate(ids)
        }
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                works[idx] = future.result()
            except Exception:
                logging.getLogger(__name__).debug("获取作品元数据失败: av_id=%s", ids[idx], exc_info=True)
                works[idx] = {"id": ids[idx], "date": "未知", "img": "", "url": "", "title": ""}
        return works

    def get_av_magnets(self, av_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        from ..magnet_search import search_magnets
        javbus_magnets: List[Dict[str, Any]] = []
        try:
            self._javbus_limiter.wait()
            code, magnets = self.javbus.get_av_magnets(av_id, is_uncensored=self.uncensored)
            if code == 200 and magnets:
                javbus_magnets = [{"title": m.get("title", ""), "size": m.get("size", ""), "magnet": m.get("magnet", "")} for m in magnets[:limit]]
        except Exception:
            logging.getLogger(__name__).debug("获取JavBus磁力链接失败: av_id=%s", av_id, exc_info=True)
        sukebei_magnets = search_magnets(av_id, max(0, limit - len(javbus_magnets)), 20)
        seen: set = set()
        result: List[Dict[str, Any]] = []
        for m in javbus_magnets + sukebei_magnets:
            magnet = m.get("magnet", "").strip()
            if not magnet or magnet in seen:
                continue
            seen.add(magnet)
            result.append(m)
            if len(result) >= limit:
                break
        return result
