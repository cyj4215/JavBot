import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            locale='zh-CN',
        )
        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)

        url = 'https://javdb.com/rankings'
        print(f'Navigating to {url}')
        await page.goto(url, wait_until='networkidle', timeout=30000)

        current_url = page.url
        print(f'Current URL: {current_url}')

        await asyncio.sleep(3)

        html = await page.content()
        print(f'HTML length: {len(html)}')

        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('title')
        print('Title:', title.get_text() if title else 'No title')

        # Check for Cloudflare
        if 'Just a moment' in html:
            print('Cloudflare detected!')

        # Look for actress names in ranking
        for sel in ['.rank-item', '.ranking-item', '[class*="rank"]', '.item', '.box']:
            elems = soup.select(sel)
            texts = [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]
            if texts:
                print(f'Selector {sel}: {len(elems)} items, first 3: {texts[:3]}')

        # Check all links
        links = soup.find_all('a')
        for link in links:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            if text and len(text) > 1 and len(text) < 20:
                print(f'Link: {text} -> {href[:60]}')

        await browser.close()

asyncio.run(test())
