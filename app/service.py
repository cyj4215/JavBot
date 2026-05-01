from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from jvav import JavBusUtil, JavDbUtil

from .cache import TTLCache
from .http_utils import build_retry_session
from .rate_limiter import RateLimiter
from .services import JavBusService, JavDbService, NameMatchService, RankService, WikiService

try:
    from opencc import OpenCC
except Exception:
    logging.getLogger(__name__).debug("OpenCC导入失败", exc_info=True)
    OpenCC = None


@dataclass
class ActressProfile:
    found: bool
    query: str
    star_name: Optional[str] = None
    star_id: Optional[str] = None
    wiki_title: Optional[str] = None
    wiki_url: Optional[str] = None
    latest_works: Optional[List[Dict[str, Any]]] = None
    top_ids: Optional[List[str]] = None
    top_works: Optional[List[Dict[str, Any]]] = None
    suggestions: Optional[List[str]] = None
    matched_name: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None


class ActressService:
    """门面类：将请求委托给各子服务，保持公共 API 不变。"""

    def __init__(
        self,
        proxy_addr: str = "",
        latest_limit: int = 5,
        top_limit: int = 5,
        profile_cache_ttl: int = 1800,
        rank_cache_ttl: int = 900,
        uncensored: bool = False,
        *,
        wiki_service: Optional[WikiService] = None,
        javbus_service: Optional[JavBusService] = None,
        rank_service: Optional[RankService] = None,
        name_match_service: Optional[NameMatchService] = None,
    ):
        self.latest_limit = latest_limit
        self.top_limit = top_limit
        self.proxy_addr = proxy_addr
        self.uncensored = uncensored

        self.javbus = JavBusUtil(proxy_addr=proxy_addr, use_cache=True)
        self.javdb = JavDbUtil(proxy_addr=proxy_addr, use_cache=True)
        self.s2t = OpenCC("s2t") if OpenCC else None
        self.t2s = OpenCC("t2s") if OpenCC else None
        self.wiki_user_agent = "tg-jvav-bot/1.0 (https://t.me/My_JavBot_bot)"
        self.http = build_retry_session(proxy_addr=proxy_addr)

        self.profile_cache: TTLCache = TTLCache(max_size=2048, default_ttl=profile_cache_ttl)
        self.rank_cache: TTLCache = TTLCache(max_size=256, default_ttl=rank_cache_ttl)
        self.av_meta_cache: TTLCache = TTLCache(max_size=4096, default_ttl=43200)
        self.wiki_page_cache: TTLCache = TTLCache(max_size=2048, default_ttl=3600)
        self._javbus_limiter: RateLimiter = RateLimiter(calls_per_second=0.5)
        self._javdb_limiter: RateLimiter = RateLimiter(calls_per_second=0.5)
        self._wiki_limiter: RateLimiter = RateLimiter(calls_per_second=1.0)

        self.alias_map: Dict[str, str] = NameMatchService._default_alias_map()

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
        self._javdb_svc = JavDbService(
            javdb_util=self.javdb,
            av_meta_cache=self.av_meta_cache,
            javdb_limiter=self._javdb_limiter,
            uncensored=uncensored,
        )
        self._rank_svc = rank_service or RankService(
            rank_cache=self.rank_cache,
        )
        self._name_match_svc = name_match_service or NameMatchService(
            javbus_util=self.javbus,
            s2t=self.s2t,
            t2s=self.t2s,
            javbus_limiter=self._javbus_limiter,
        )

    async def get_hot_star_rankings(self, limit: int = 20, page: int = 1) -> List[Dict[str, Any]]:
        return await self._rank_svc.get_hot_star_rankings(limit=limit, page=page)

    async def start_rank_background_refresh(self) -> None:
        await self._rank_svc.start_background_refresh()

    def get_av_magnets(self, av_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self._javbus_svc.get_av_magnets(av_id, limit=limit)

    def get_av_meta(self, av_id: str) -> Dict[str, Any]:
        return self._javbus_svc.get_av_meta(av_id)

    def get_rank_cache(self, key: tuple) -> Any:
        return self.rank_cache.get(key)

    def _resolve_name_sync(self, name: str):
        """Sync name resolution: candidates -> find_star -> wiki aliases -> fuzzy fallback.

        Runs in thread pool via asyncio.to_thread to avoid blocking the event loop.
        """
        candidates = self._name_match_svc.name_candidates(name)
        matched_name, star = self._name_match_svc.find_star(candidates)

        if not star:
            for cand in list(candidates):
                for alias in self._wiki_svc.wiki_aliases(
                    cand,
                    normalize_name_fn=self._name_match_svc._normalize_name,
                    contains_cjk_fn=self._name_match_svc._contains_cjk,
                ):
                    if alias not in candidates:
                        candidates.append(alias)
            matched_name, star = self._name_match_svc.find_star(candidates)

        suggestions: list = []
        if not star:
            seen: set = set()
            for cand in candidates[:4]:
                code, names = self.javbus.fuzzy_search_stars(cand)
                if code != 200 or not names:
                    continue
                for n in names:
                    if n not in seen:
                        seen.add(n)
                        suggestions.append(n)
                    if len(suggestions) >= 10:
                        break
                if len(suggestions) >= 10:
                    break

        return matched_name, star, suggestions

    async def query_profile_async(self, name: str) -> ActressProfile:
        profile_cache_key = ("profile", self._name_match_svc._normalize_name(name), self.latest_limit, self.top_limit)
        cached = self.profile_cache.get(profile_cache_key)
        if cached is not None:
            return ActressProfile(**cached)

        matched_name, star, suggestions = await asyncio.to_thread(
            self._resolve_name_sync, name
        )

        if not star:
            result = ActressProfile(
                found=False,
                query=name,
                suggestions=suggestions,
            )
            self.profile_cache.set(profile_cache_key, result.__dict__)
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

        latest_works: List[Dict[str, Any]] = []
        top_ids: List[str] = []
        wiki_page: Dict[str, Any] = {}
        extra_info: Dict[str, Any] = {}

        javdb_task = self._javdb_svc.get_latest_works(star_name, limit=self.latest_limit)
        top_ids_task = asyncio.to_thread(load_top_ids)
        wiki_task = asyncio.to_thread(load_wiki_extra)

        javdb_result, top_ids_result, wiki_result = await asyncio.gather(
            javdb_task, top_ids_task, wiki_task, return_exceptions=True
        )

        if isinstance(javdb_result, Exception):
            logging.getLogger(__name__).debug(
                f"JavDb 获取最新作品失败，回退到 JavBus: {star_name}", exc_info=javdb_result
            )
        elif javdb_result:
            latest_works = javdb_result
            logging.getLogger(__name__).info(
                f"使用 JavDb 获取 {star_name} 的最新作品: {len(javdb_result)} 部"
            )

        if not latest_works:
            try:
                latest_works = await asyncio.to_thread(load_latest)
            except Exception:
                logging.getLogger(__name__).debug("获取最新作品失败", exc_info=True)
                latest_works = []

        if isinstance(top_ids_result, Exception):
            logging.getLogger(__name__).debug("获取热门作品失败", exc_info=top_ids_result)
            top_ids = []
        else:
            top_ids = top_ids_result

        if isinstance(wiki_result, Exception):
            logging.getLogger(__name__).debug("获取维基信息失败", exc_info=wiki_result)
            wiki_page, extra_info = {}, {}
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
        self.profile_cache.set(profile_cache_key, result.__dict__)
        return result
