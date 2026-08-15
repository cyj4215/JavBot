"""JavDb scraper using curl_cffi (primary) with subprocess curl fallback.

JavDb uses Cloudflare Bot Management that blocks Python's TLS fingerprint
(OpenSSL/urllib3 JA3 fingerprint). curl_cffi emulates browser TLS fingerprint.
On macOS, subprocess curl uses SecureTransport which also bypasses Cloudflare.

Used as secondary data source: query results merge with JavBus (dedup by AV ID).
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import time
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..cache import TTLCache
from ..models.actors import ActorSearchResult
from ..models.works import JavDbWork

logger = logging.getLogger(__name__)

_CURL_TIMEOUT = 25
_CURL_HEADERS = [
    "-H",
    "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "-H",
    "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "-H",
    "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
    "-H",
    "Referer: https://www.google.com/",
    "-H",
    "DNT: 1",
]

try:
    from curl_cffi import requests as curl_requests

    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False


def _fetch(url: str) -> str | None:
    """curl_cffi (preferred) or subprocess curl (fallback)."""
    if _HAS_CURL_CFFI:
        try:
            resp = curl_requests.get(url, impersonate="chrome131", timeout=_CURL_TIMEOUT)
            from ..health import SourceStatus

            SourceStatus.ok("javdb")
            return resp.text  # type: ignore[no-any-return]
        except Exception as e:
            logger.warning("curl_cffi failed: %s, falling back to subprocess curl", e)
    result = _curl_get(url)
    from ..health import SourceStatus

    if result is None:
        SourceStatus.fail("javdb", "fetch failed")
    else:
        SourceStatus.ok("javdb")
    return result


def _curl_get(url: str) -> str | None:
    """Run curl and return HTML body, or None on failure."""
    try:
        result = subprocess.run(
            ["curl", "-sL", "--max-time", str(_CURL_TIMEOUT), *_CURL_HEADERS, url],
            capture_output=True,
            text=True,
            timeout=_CURL_TIMEOUT + 5,
        )
        if result.returncode != 0:
            logger.warning("curl failed (rc=%d): %.100s", result.returncode, url)
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.warning("curl timeout: %.100s", url)
        return None
    except Exception as e:
        logger.warning("curl error: %s for %.100s", e, url)
        return None


def _parse_actor_search(html: str) -> list[ActorSearchResult]:
    """Parse actor search results (actor-box)."""
    soup = BeautifulSoup(html, "html.parser")
    actors: list[ActorSearchResult] = []

    title_tag = soup.find("title")
    if title_tag and (
        "cloudflare" in title_tag.get_text().lower() or "challenge" in title_tag.get_text().lower()
    ):
        logger.warning("JavDb returned Cloudflare challenge page")
        return actors

    for box in soup.find_all(class_="actor-box"):
        a_tag = box.find("a")
        if not a_tag:
            continue

        name = ""
        strong = a_tag.find("strong")
        if strong:
            name = strong.get_text(strip=True)
        if not name:
            name = str(a_tag.get("title", "")).strip()

        href = str(a_tag.get("href", ""))
        actor_url = f"https://javdb.com{href}" if href and not href.startswith("http") else href

        img = ""
        img_tag = box.find("img")
        if img_tag:
            img = str(img_tag.get("src", img_tag.get("data-src", "")))
            if img and not img.startswith("http"):
                img = f"https://javdb.com{img}"

        if name:
            actors.append(ActorSearchResult(name=name, url=actor_url, avatar=img))

    return actors


def _parse_movie_list(html: str, limit: int = 10) -> list[JavDbWork]:
    """Parse movie-list from actor page."""

    soup = BeautifulSoup(html, "html.parser")
    works: list[JavDbWork] = []

    title_tag = soup.find("title")
    if title_tag and (
        "cloudflare" in title_tag.get_text().lower() or "challenge" in title_tag.get_text().lower()
    ):
        logger.warning("JavDb returned Cloudflare challenge page")
        return works

    movie_list = soup.find(class_="movie-list")
    if not movie_list:
        logger.debug("No .movie-list found on JavDb page")
        return works

    for item in movie_list.find_all("a", class_="box", limit=limit):
        try:
            strong_tag = item.find("strong")
            av_id = strong_tag.get_text(strip=True) if strong_tag else ""

            if not av_id:
                uid_tag = item.find(class_="uid")
                av_id = uid_tag.get_text(strip=True) if uid_tag else ""

            title_tag_elem = item.find(class_="video-title")
            title = ""
            if title_tag_elem:
                title_text = title_tag_elem.get_text(strip=True)
                title = title_text.replace(av_id, "").strip()

            meta_tag = item.find(class_="meta")
            date = ""
            if meta_tag:
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", meta_tag.get_text())
                if date_match:
                    date = date_match.group(1)

            img_tag = item.find("img")
            img = str(img_tag.get("src", "")) if img_tag else ""
            if not img:
                img = str(img_tag.get("data-src", "")) if img_tag else ""

            url = str(item.get("href", ""))
            if url and not url.startswith("http"):
                url = f"https://javdb.com{url}"

            if av_id:
                works.append(
                    JavDbWork(
                        id=av_id,
                        title=title,
                        date=date or "未知",
                        img=img,
                        url=url,
                    )
                )
        except Exception:
            continue

    return works


class JavDbScraper:
    """High-level JavDb scraping with caching."""

    def __init__(self, cache: TTLCache | None = None, cache_ttl: int = 21600):
        self._cache = cache or TTLCache(max_size=512, default_ttl=cache_ttl)
        self._last_request = 0.0
        self._request_lock = asyncio.Lock()

    async def _rate_limited_fetch(self, url: str) -> str | None:
        """Fetch URL with rate limiting via thread pool."""
        async with self._request_lock:
            now = time.monotonic()
            since_last = now - self._last_request
            if since_last < 2.0:
                await asyncio.sleep(2.0 - since_last)
            self._last_request = time.monotonic()
            return await asyncio.to_thread(_fetch, url)

    async def search_actress(self, name: str) -> ActorSearchResult | None:
        """Search for an actress on JavDb. Returns first match or None."""
        cache_key = ("javdb_search", name.lower().strip())
        cached = self._cache.get(cache_key)
        if cached is not None:
            return ActorSearchResult.model_validate(cached)

        url = f"https://javdb.com/search?q={quote(name)}&f=actor"
        html = await self._rate_limited_fetch(url)
        if not html:
            return None

        actors = _parse_actor_search(html)
        if not actors:
            return None

        result = actors[0]
        self._cache.set(cache_key, result.model_dump(mode="json"))
        return result

    async def get_actor_works(self, actor_url: str, limit: int = 10) -> list[JavDbWork]:
        """Get works list from an actor's JavDb page."""
        cache_key = ("javdb_works", actor_url, limit)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [JavDbWork.model_validate(w) for w in cached]

        html = await self._rate_limited_fetch(actor_url)
        if not html:
            return []

        works = _parse_movie_list(html, limit=limit)
        if works:
            self._cache.set(cache_key, [w.model_dump(mode="json") for w in works])
        return works

    async def get_actress_works(self, name: str, limit: int = 10) -> list[JavDbWork]:
        """Get works for an actress by name. High-level: search then fetch works.

        Returns empty list if actress not found or fetch fails.
        """
        actor = await self.search_actress(name)
        if not actor:
            return []
        return await self.get_actor_works(actor.url, limit=limit)

    async def get_actors_ranking(self, limit: int = 20, page: int = 1) -> list[ActorSearchResult]:
        """Scrape JavDb actor listing (sorted by popularity). Uses curl (Cloudflare bypass).

        Returns list of ActorSearchResult with keys: name, url, avatar.
        Empty list on failure or Cloudflare challenge.
        """
        cache_key = ("javdb_actors", page)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [ActorSearchResult.model_validate(a) for a in cached]

        url = f"https://javdb.com/actors?page={page}"
        html = await self._rate_limited_fetch(url)
        if not html:
            return []

        actors = _parse_actor_search(html)
        if actors:
            self._cache.set(cache_key, [a.model_dump(mode="json") for a in actors])
        return actors[:limit]
