"""Find DMM API endpoint for actress rankings via Playwright."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


async def main():
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    extra_http_headers = {
        "Accept-Language": "ja-JP,ja;q=0.9",
    }
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        locale="ja-JP",
        extra_http_headers=extra_http_headers,
        storage_state={
            "cookies": [
                {"name": "age_check_done", "value": "1", "domain": ".dmm.co.jp", "path": "/"},
            ]
        },
    )

    page = await context.new_page()

    # Intercept network requests and responses
    api_requests = []

    async def on_response(resp):
        url = resp.url
        if "graphql" in url:
            try:
                body = await resp.body()
                info = {"url": url, "status": resp.status, "body": body[:1000].decode("utf-8", errors="replace")}
                api_requests.append(info)
            except Exception:
                pass

    page.on("response", on_response)

    url = "https://video.dmm.co.jp/av/ranking/?term=monthly&type=actress"
    log.info("Navigating to %s", url)
    await page.goto(url, wait_until="networkidle", timeout=60000)
    await asyncio.sleep(5)

    log.info("GraphQL responses captured: %d", len(api_requests))
    for req in api_requests:
        log.info("  status=%s body=%s", req["status"], req["body"][:300])

    # Also check page title
    title = await page.title()
    log.info("Page title: %s", title)

    # Try to get ranking data from page
    try:
        items = await page.evaluate("""() => {
            const items = document.querySelectorAll('a[href*="actress"] img, [class*="actress"], a[href*="digital"]');
            const results = [];
            document.querySelectorAll('a[href*="actress"]').forEach(a => {
                const img = a.querySelector('img');
                const name = img ? img.getAttribute('alt') || img.title || '' : a.textContent.trim();
                if (name && name.length > 0 && name.length < 30) {
                    results.push({name, href: a.href, rank: a.querySelector('.rank')?.textContent || ''});
                }
            });
            return results.slice(0, 30);
        }""")
        log.info("Actress links found: %d", len(items))
        for item in items:
            log.info("  %s", item)
    except Exception as e:
        log.warning("evaluate failed: %s", e)

    # Also dump visible text for debugging
    try:
        text = await page.evaluate("() => document.body.innerText.slice(0, 3000)")
        log.info("Visible text:\\n%s", text)
    except Exception as e:
        log.warning("text extraction failed: %s", e)

    await context.close()
    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
