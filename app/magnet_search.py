import logging
import time
from collections import OrderedDict
from threading import RLock
from typing import Dict, List

import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry

BASE_URL = "https://sukebei.nyaa.si"
DEFAULT_TIMEOUT = 20
DEFAULT_LIMIT = 5
DEFAULT_CACHE_TTL = 300
DEFAULT_CACHE_SIZE = 512
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

_CACHE = OrderedDict()
_CACHE_LOCK = RLock()


def _build_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"user-agent": UA})
    return session


_SESSION = _build_session()


def _cache_get(key):
    now = time.time()
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if not item:
            return None
        expire_at, value = item
        if expire_at < now:
            _CACHE.pop(key, None)
            return None
        _CACHE.move_to_end(key)
        return [dict(x) for x in value]


def _cache_set(key, value):
    expire_at = time.time() + DEFAULT_CACHE_TTL
    with _CACHE_LOCK:
        _CACHE[key] = (expire_at, [dict(x) for x in value])
        _CACHE.move_to_end(key)
        while len(_CACHE) > DEFAULT_CACHE_SIZE:
            _CACHE.popitem(last=False)


def search_magnets(query: str, limit: int = DEFAULT_LIMIT, timeout: int = DEFAULT_TIMEOUT) -> List[Dict[str, str]]:
    q = (query or "").strip()
    if not q:
        return []

    limit = max(1, min(limit, 10))
    timeout = max(5, min(timeout, 60))
    cache_key = (q.lower(), limit)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = _SESSION.get(
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
        _cache_set(cache_key, results)
        return results
    except Exception as exc:
        logging.getLogger(__name__).warning("parse sukebei failed: %s", exc)
        return []
