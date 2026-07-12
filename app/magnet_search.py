"""MagnetSearch: search sukebei.nyaa.si for magnet links.

Usage:
    ms = MagnetSearch(proxy="http://proxy:7890")
    links = ms.search("SSIS-123", limit=5, timeout=20)
"""
from __future__ import annotations

import logging
import os

from bs4 import BeautifulSoup

from .cache import TTLCache
from .models.magnets import MagnetLink

BASE_URL = "https://sukebei.nyaa.si"
DEFAULT_TIMEOUT = 20
DEFAULT_LIMIT = 5
DEFAULT_CACHE_TTL = int(os.getenv("MAGNET_CACHE_TTL", "300"))
DEFAULT_CACHE_SIZE = 512
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class MagnetSearch:
    """Search sukebei.nyaa.si for magnet links with caching and fallback variations."""

    def __init__(self, proxy: str = ""):
        self._cache = TTLCache(max_size=DEFAULT_CACHE_SIZE, default_ttl=DEFAULT_CACHE_TTL)
        self._proxy = proxy

    def search(
        self, query: str, limit: int = DEFAULT_LIMIT, timeout: int = DEFAULT_TIMEOUT
    ) -> list[MagnetLink]:
        q = (query or "").strip()
        if not q:
            return []
        limit = max(1, min(limit, 10))
        timeout = max(5, min(timeout, 60))
        cache_key = (q.lower(), limit)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [MagnetLink.model_validate(m) for m in cached]

        results = self._search_variations(q, limit, timeout)
        if results:
            self._cache.set(cache_key, [m.model_dump(mode="json") for m in results])
        return results

    def _do_search(self, q: str, limit: int, timeout: int) -> list[MagnetLink]:
        """Search sukebei.nyaa.si, return parsed MagnetLinks."""
        import httpx

        try:
            resp = httpx.get(
                f"{BASE_URL}/",
                params={"q": q},
                timeout=timeout,
                headers={"User-Agent": UA},
                proxy=self._proxy if self._proxy else None,
            )
            if resp.status_code != 200:
                return []
        except httpx.RequestError:
            return []

        try:
            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select("table.torrent-list tbody tr") or soup.select("tbody tr")
            results: list[MagnetLink] = []
            for row in rows:
                title_tag = row.select_one("td:nth-of-type(2) a:not(.comments)")
                magnet_tag = row.select_one('a[href^="magnet:"]')
                size_tag = row.select_one("td:nth-of-type(4)")
                if not title_tag or not magnet_tag:
                    continue
                title = str(title_tag.get("title") or title_tag.get_text(" ", strip=True) or "").strip()
                magnet = str(magnet_tag.get("href") or "").strip()
                size = str(size_tag.get_text(" ", strip=True) if size_tag else "").strip() or "Unknown"
                if not title or not magnet:
                    continue
                results.append(MagnetLink(title=title, magnet=magnet, size=size))
                if len(results) >= limit:
                    break
            return results
        except Exception as exc:
            logging.getLogger(__name__).warning("parse sukebei failed: %s", exc)
            return []

    def _search_variations(self, q: str, limit: int, timeout: int) -> list[MagnetLink]:
        """Search with fallback variations when exact query returns no results."""
        results = self._do_search(q, limit, timeout)
        if results:
            return results

        # Fallback 1: remove hyphens (MIZD-537 -> MIZD537)
        if "-" in q:
            alt = q.replace("-", "")
            if alt != q:
                results = self._do_search(alt, limit, timeout)
                if results:
                    return results

        # Fallback 2: search by prefix only (MIZD-537 -> MIZD)
        if "-" in q and len(q) > 3:
            prefix = q.split("-")[0].strip()
            if prefix:
                results = self._do_search(prefix, limit, timeout)
                if results:
                    return results

        # Fallback 3: search by numeric part (MIZD-537 -> 537)
        if "-" in q:
            parts = q.split("-")
            if len(parts) > 1 and parts[-1].strip().isdigit():
                results = self._do_search(parts[-1].strip(), limit, timeout)
                if results:
                    return results

        return []
