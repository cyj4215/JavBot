"""Test curl_cffi feasibility for JavDb scraping vs Playwright baseline.

Tests 3 scenarios:
1. curl_cffi with chrome120 impersonation
2. curl_cffi without impersonation
3. Standard requests (baseline)

Measures time, success rate, and Cloudflare bypass.
"""

import time
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

URL = "https://javdb.com/actors?page=1"


def parse_actors(html: str) -> List[Dict[str, Any]]:
    """Extract actor names and URLs from JavDb actors page HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.text.lower() if title_tag else ""

    # Check Cloudflare
    if "moment" in title or "cloudflare" in title:
        log.warning("Cloudflare challenge detected in page title")
        return []

    actors = []
    for box in soup.find_all(class_="actor-box"):
        a_tag = box.find("a")
        if not a_tag:
            continue
        strong = a_tag.find("strong")
        name = strong.get_text(strip=True) if strong else a_tag.get("title", "").strip()
        href = a_tag.get("href", "")
        if name:
            actors.append({"name": name, "url": href})
    return actors


def test_curl_cffi_impersonate() -> List[Dict[str, Any]]:
    """Test curl_cffi with Chrome 120 impersonation."""
    log.info("=== Test 1: curl_cffi with impersonate=chrome120 ===")
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        log.error("curl_cffi not installed")
        return []

    start = time.time()
    try:
        resp = curl_requests.get(URL, impersonate="chrome120", timeout=30)
        elapsed = time.time() - start
        log.info("Status: %d, Time: %.2fs", resp.status_code, elapsed)
        actors = parse_actors(resp.text)
        log.info("Actors found: %d", len(actors))
        if actors:
            log.info("First 3: %s", [a["name"] for a in actors[:3]])
        return actors
    except Exception as e:
        elapsed = time.time() - start
        log.error("Failed after %.2fs: %s", elapsed, e)
        return []


def test_curl_cffi_no_impersonate() -> List[Dict[str, Any]]:
    """Test curl_cffi without impersonation."""
    log.info("=== Test 2: curl_cffi without impersonation ===")
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        log.error("curl_cffi not installed")
        return []

    start = time.time()
    try:
        resp = curl_requests.get(URL, timeout=30)
        elapsed = time.time() - start
        log.info("Status: %d, Time: %.2fs", resp.status_code, elapsed)
        actors = parse_actors(resp.text)
        log.info("Actors found: %d", len(actors))
        return actors
    except Exception as e:
        elapsed = time.time() - start
        log.error("Failed after %.2fs: %s", elapsed, e)
        return []


def test_requests_baseline() -> List[Dict[str, Any]]:
    """Test standard requests library as baseline."""
    log.info("=== Test 3: standard requests (baseline) ===")
    import requests

    start = time.time()
    try:
        resp = requests.get(URL, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })
        elapsed = time.time() - start
        log.info("Status: %d, Time: %.2fs", resp.status_code, elapsed)
        actors = parse_actors(resp.text)
        log.info("Actors found: %d", len(actors))
        return actors
    except Exception as e:
        elapsed = time.time() - start
        log.error("Failed after %.2fs: %s", elapsed, e)
        return []


if __name__ == "__main__":
    log.info("Testing curl_cffi for JavDb scraping feasibility")
    log.info("URL: %s", URL)

    r1 = test_curl_cffi_impersonate()
    r2 = test_curl_cffi_no_impersonate()
    r3 = test_requests_baseline()

    log.info("=" * 50)
    log.info("Results:")
    log.info("  curl_cffi + impersonate: %d actors", len(r1))
    log.info("  curl_cffi no impersonate: %d actors", len(r2))
    log.info("  requests baseline:       %d actors", len(r3))
    log.info("=" * 50)

    if r1:
        log.info("SUCCESS: curl_cffi with impersonation works for JavDb!")
    else:
        log.warning("curl_cffi with impersonation did NOT work for JavDb")

    if r1 and not r3:
        log.info("curl_cffi bypasses Cloudflare while requests does not - good sign")
