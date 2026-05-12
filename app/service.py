from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from jvav import JavBusUtil

from .cache import TTLCache
from .http_utils import build_retry_session
from .models import ActressProfile
from .services.i18n_service import I18nService
from .services.javdb_scraper import JavDbScraper
from .services.rank_service import RankService
from .rate_limiter import RateLimiter
from .services import JavBusService, NameMatchService, ProfileResolver, WikiService
from .services.text_utils import normalize_name

try:
    from opencc import OpenCC
except Exception:
    logging.getLogger(__name__).debug("OpenCC导入失败", exc_info=True)
    OpenCC = None


class ActressService:
    """门面类：将请求委托给各子服务，保持公共 API 不变。"""

    def __init__(
        self,
        proxy_addr: str = "",
        latest_limit: int = 5,
        top_limit: int = 5,
        profile_cache_ttl: int = 1800,
        uncensored: bool = False,
        rank_cache_ttl: int = 900,
        i18n_default_language: str = "zh_CN",
        *,
        wiki_service: Optional[WikiService] = None,
        javbus_service: Optional[JavBusService] = None,
        name_match_service: Optional[NameMatchService] = None,
    ):
        self.latest_limit = latest_limit
        self.top_limit = top_limit
        self.proxy_addr = proxy_addr
        self.uncensored = uncensored

        self.javbus = JavBusUtil(proxy_addr=proxy_addr, use_cache=True)
        self.s2t = OpenCC("s2t") if OpenCC else None
        self.t2s = OpenCC("t2s") if OpenCC else None
        self.wiki_user_agent = "tg-jvav-bot/1.0 (https://t.me/My_JavBot_bot)"
        self.http = build_retry_session(proxy_addr=proxy_addr)

        self.profile_cache: TTLCache = TTLCache(max_size=2048, default_ttl=profile_cache_ttl)
        self.av_meta_cache: TTLCache = TTLCache(max_size=4096, default_ttl=43200)
        self.wiki_page_cache: TTLCache = TTLCache(max_size=2048, default_ttl=3600)
        self.rank_cache: TTLCache = TTLCache(max_size=32, default_ttl=rank_cache_ttl)
        self._javdb_cache: TTLCache = TTLCache(max_size=512, default_ttl=21600)
        self._javdb_scraper = JavDbScraper(cache=self._javdb_cache)
        self._javbus_limiter: RateLimiter = RateLimiter(calls_per_second=0.5)
        self._wiki_limiter: RateLimiter = RateLimiter(calls_per_second=1.0)

        self._rank_svc = RankService(rank_cache=self.rank_cache, refresh_interval=rank_cache_ttl)
        self.i18n = I18nService(default_lang=i18n_default_language)

        self._wiki_svc = wiki_service or WikiService(
            proxy_addr=proxy_addr,
            wiki_user_agent=self.wiki_user_agent,
            http_session=self.http,
            wiki_page_cache=self.wiki_page_cache,
            wiki_limiter=self._wiki_limiter,
        )
        self._javbus_svc = javbus_service or JavBusService(
            javbus_util=self.javbus,
            av_meta_cache=self.av_meta_cache,
            javbus_limiter=self._javbus_limiter,
            uncensored=uncensored,
        )
        self._name_match_svc = name_match_service or NameMatchService(
            javbus_util=self.javbus,
            s2t=self.s2t,
            t2s=self.t2s,
            javbus_limiter=self._javbus_limiter,
        )
        self._resolver = ProfileResolver(
            name_match_svc=self._name_match_svc,
            wiki_svc=self._wiki_svc,
            javbus=self.javbus,
            javbus_limiter=self._javbus_limiter,
        )

    def get_av_magnets(self, av_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self._javbus_svc.get_av_magnets(av_id, limit=limit)

    def get_av_meta(self, av_id: str) -> Dict[str, Any]:
        return self._javbus_svc.get_av_meta(av_id)

    def get_rank_cache(self, key) -> Any:
        return self.rank_cache.get(key)

    async def get_hot_star_rankings(self, limit: int = 20, page: int = 1) -> List[Dict[str, Any]]:
        return await self._rank_svc.get_hot_star_rankings(limit=limit, page=page)

    async def start_rank_background_refresh(self) -> None:
        await self._rank_svc.start_background_refresh()

    async def query_profile_async(self, name: str) -> ActressProfile:
        cache_key = ("profile", normalize_name(name), self.latest_limit, self.top_limit)
        cached = self.profile_cache.get(cache_key)
        if cached is not None:
            return ActressProfile(**cached)

        matched_name, star, suggestions = await asyncio.to_thread(
            self._resolver.resolve, name
        )

        if not star:
            result = ActressProfile(
                found=False,
                query=name,
                suggestions=suggestions,
            )
            self.profile_cache.set(cache_key, result.__dict__)
            return result

        star_name = star.get("star_name", name)
        star_id = star.get("star_id", "")

        def load_latest() -> List[Dict[str, Any]]:
            code, ids = self.javbus.get_new_ids_by_star_name(star_name)
            if code == 200 and ids:
                return self._javbus_svc.build_latest_works(ids[: self.latest_limit])
            return []

        def load_top_ids() -> List[str]:
            self._javbus_limiter.wait()
            code, ids = self.javbus.get_id_by_star_name(star_name)
            if code == 200 and ids:
                return ids[: self.top_limit]
            return []

        def load_wiki_extra() -> Tuple[Dict[str, Any], Dict[str, Any]]:
            wiki_page = self._wiki_svc.wiki_page_by_lang(star_name, from_lang="ja", to_lang="zh")
            extra_info = self._wiki_svc.get_star_extra_info(wiki_page.get("url", ""))
            return wiki_page, extra_info

        latest_result, top_ids_result, wiki_result, javdb_result = await asyncio.gather(
            asyncio.to_thread(load_latest),
            asyncio.to_thread(load_top_ids),
            asyncio.to_thread(load_wiki_extra),
            self._javdb_scraper.get_actress_works(star_name, limit=self.latest_limit),
            return_exceptions=True,
        )

        latest_works = []
        if isinstance(latest_result, Exception):
            logging.getLogger(__name__).debug("获取最新作品失败", exc_info=latest_result)
        else:
            latest_works = latest_result

        # Merge JavDb works into latest_works (dedup by AV ID)
        if not isinstance(javdb_result, Exception) and javdb_result:
            seen_ids = {w.get("id") for w in latest_works if w.get("id")}
            for w in javdb_result:
                if w.get("id") and w["id"] not in seen_ids:
                    seen_ids.add(w["id"])
                    latest_works.append(w)

        top_ids: List[str] = []
        if isinstance(top_ids_result, Exception):
            logging.getLogger(__name__).debug("获取热门作品失败", exc_info=top_ids_result)
        else:
            top_ids = top_ids_result

        wiki_page: Dict[str, Any] = {}
        extra_info: Dict[str, Any] = {}
        if isinstance(wiki_result, Exception):
            logging.getLogger(__name__).debug("获取维基信息失败", exc_info=wiki_result)
        else:
            wiki_page, extra_info = wiki_result

        result = ActressProfile(
            found=True,
            query=name,
            star_name=star_name,
            star_id=star_id,
            wiki_title=wiki_page.get("title"),
            wiki_url=wiki_page.get("url"),
            latest_works=latest_works,
            top_ids=top_ids,
            matched_name=matched_name,
            extra_info=extra_info,
        )
        self.profile_cache.set(cache_key, result.__dict__)
        return result
