from __future__ import annotations

import atexit
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from ..models.magnets import MagnetLink
from ..models.works import JavBusWork

if TYPE_CHECKING:
    from jvav import JavBusUtil

    from ..cache import TTLCache
    from ..rate_limiter import RateLimiter


class JavBusService:
    """JavBus AV 元数据与磁力链接子服务。"""

    def __init__(
        self,
        javbus_util: JavBusUtil,
        av_meta_cache: TTLCache,
        javbus_limiter: RateLimiter,
        uncensored: bool = False,
        magnet_search_module: Any = None,
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

    def get_av_meta(self, av_id: str, is_uncensored: bool | None = None) -> JavBusWork:
        if is_uncensored is None:
            is_uncensored = self.uncensored
        cached = self.av_meta_cache.get((av_id, is_uncensored))
        if cached is not None:
            return JavBusWork.model_validate(cached)

        try:
            self._javbus_limiter.wait()
            code, av = self.javbus.get_av_by_id(av_id, is_nice=False, is_uncensored=is_uncensored)
            if code == 200 and isinstance(av, dict):
                date = (av.get("date") or "").strip()
                img = (av.get("img") or "").strip()
                url = (av.get("url") or "").strip()
                title = (av.get("title") or "").strip()

                code, magnets = self.javbus.get_av_magnets(av_id, is_uncensored=is_uncensored)
                magnet_links = []
                if code == 200 and magnets:
                    magnet_links = [
                        MagnetLink(
                            title=m.get("title", ""),
                            magnet=m.get("magnet", ""),
                            size=m.get("size", ""),
                        )
                        for m in magnets[:3]
                    ]

                result = JavBusWork(
                    id=av_id,
                    title=title,
                    date=date or "未知",
                    img=img if img.startswith("http") else "",
                    url=url,
                    magnets=magnet_links,
                )
                self.av_meta_cache.set((av_id, is_uncensored), result.model_dump(mode="json"))
                return result
        except Exception:
            logging.getLogger(__name__).debug("获取AV元数据失败: av_id=%s", av_id, exc_info=True)

        return JavBusWork(id=av_id)

    def build_latest_works(self, ids: list[str]) -> list[JavBusWork]:
        works: list[JavBusWork] = []
        for av_id in ids[:20]:
            work = self.get_av_meta(av_id)
            works.append(work)
        return works

    def get_av_magnets(self, av_id: str, limit: int = 5) -> list[MagnetLink]:
        from ..magnet_search import MagnetSearch

        javbus_magnets: list[MagnetLink] = []
        try:
            self._javbus_limiter.wait()
            code, magnets = self.javbus.get_av_magnets(av_id, is_uncensored=self.uncensored)
            if code == 200 and magnets:
                javbus_magnets = [
                    MagnetLink(
                        title=m.get("title", ""), magnet=m.get("magnet", ""), size=m.get("size", "")
                    )
                    for m in magnets[:limit]
                ]
        except Exception:
            logging.getLogger(__name__).debug(
                "获取JavBus磁力链接失败: av_id=%s", av_id, exc_info=True
            )

        sukebei_magnets = MagnetSearch().search(
            av_id, max(0, limit - len(javbus_magnets)), 20
        )

        seen: set = set()
        result: list[MagnetLink] = []
        for m in javbus_magnets + sukebei_magnets:
            if not m.magnet or m.magnet in seen:
                continue
            seen.add(m.magnet)
            result.append(m)
            if len(result) >= limit:
                break
        return result
