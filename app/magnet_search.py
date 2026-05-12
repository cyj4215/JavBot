import logging
import os
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from .cache import TTLCache
from .http_utils import build_retry_session

BASE_URL = "https://sukebei.nyaa.si"
DEFAULT_TIMEOUT = 20
DEFAULT_LIMIT = 5
DEFAULT_CACHE_TTL = 300
DEFAULT_CACHE_SIZE = 512
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

_cache = TTLCache(max_size=DEFAULT_CACHE_SIZE, default_ttl=DEFAULT_CACHE_TTL)
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        proxy_addr = os.getenv("HTTP_PROXY", "").strip()
        _session = build_retry_session(proxy_addr=proxy_addr)
        _session.headers.update({"user-agent": UA})
    return _session


def search_magnets(query: str, limit: int = DEFAULT_LIMIT, timeout: int = DEFAULT_TIMEOUT) -> List[Dict[str, str]]:
    q = (query or "").strip()
    if not q:
        return []

    limit = max(1, min(limit, 10))
    timeout = max(5, min(timeout, 60))
    cache_key = (q.lower(), limit)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = _get_session().get(
            f"{BASE_URL}/",
            params={"q": q},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return []
    except requests.RequestException:
        return []

    try:
        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table.torrent-list tbody tr")
        if not rows:
            rows = soup.select("tbody tr")
        results: List[Dict[str, str]] = []
        for row in rows:
            title_tag = row.select_one("td:nth-of-type(2) a:not(.comments)")
            magnet_tag = row.select_one('a[href^="magnet:"]')
            size_tag = row.select_one("td:nth-of-type(4)")
            if not title_tag or not magnet_tag:
                continue

            title = (title_tag.get("title") or title_tag.get_text(" ", strip=True) or "").strip()
            magnet = (magnet_tag.get("href") or "").strip()
            size = (size_tag.get_text(" ", strip=True) if size_tag else "").strip() or "Unknown"
            if not title or not magnet:
                continue

            results.append(
                {
                    "title": title,
                    "magnet": magnet,
                    "size": size,
                }
            )
            if len(results) >= limit:
                break
        _cache.set(cache_key, results)
        return results
    except Exception as exc:
        logging.getLogger(__name__).warning("parse sukebei failed: %s", exc)
        return []
