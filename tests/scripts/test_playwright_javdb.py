"""End-to-end test: Playwright scraping JavDb actors page."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


async def main():
    from playwright.async_api import async_playwright

    STEALTH = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [
        {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
        {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
        {name: 'Native Client', filename: 'internal-nacl-plugin'}
    ]});
    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
    window.chrome = {runtime: {}};
    """

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--window-size=1920,1080",
        ],
    )

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    page = await context.new_page()
    await page.add_init_script(STEALTH)

    url = "https://javdb.com/actors?page=1"
    log.info("Navigating to %s", url)

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        log.info("Response status: %s", response.status if response else "N/A")
    except Exception as e:
        log.error("Navigation failed: %s", e)
        await browser.close()
        await pw.stop()
        return

    title = await page.title()
    log.info("Page title: %s", title)

    if "moment" in title.lower() or "cloudflare" in title.lower():
        log.warning("Cloudflare challenge detected!")
        log.info("Waiting for challenge to resolve...")
        try:
            await page.wait_for_function(
                "() => !document.title.toLowerCase().includes('moment') && !document.title.toLowerCase().includes('cloudflare')",
                timeout=30000,
            )
            title = await page.title()
            log.info("After challenge - title: %s", title)
        except Exception:
            log.warning("Challenge wait timed out")

    try:
        await page.wait_for_selector(".actor-box", timeout=15000)
        log.info("Actor boxes found!")
    except Exception:
        log.warning("No .actor-box elements found")

    content = await page.content()
    log.info("HTML length: %d", len(content))

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")
    boxes = soup.find_all(class_="actor-box")
    log.info("Actor box count: %d", len(boxes))

    if boxes:
        for b in boxes[:5]:
            a = b.find("a")
            if a:
                strong = a.find("strong")
                name = strong.get_text(strip=True) if strong else a.get("title", "")
                log.info("  Actor: %s", name)

    await context.close()
    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
