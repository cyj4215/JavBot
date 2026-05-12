import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ja-JP',
        )
        page = await context.new_page()

        # Stealth script
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en'] });
        """)

        # Try the new URL directly
        url = 'https://video.dmm.co.jp/av/ranking/?term=monthly&type=actress'
        print(f'Navigating to {url}')
        await page.goto(url, wait_until='networkidle', timeout=30000)

        current_url = page.url
        print(f'Current URL: {current_url}')

        # Wait for content
        await asyncio.sleep(3)

        html = await page.content()
        print(f'HTML length: {len(html)}')

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        title = soup.find('title')
        print('Title:', title.get_text() if title else 'No title')

        # Check for login requirement
        if 'ログイン' in html or 'login' in html.lower():
            print('LOGIN REQUIRED')

        # Look for ranking content
        for sel in ['.rank-name', '.actress-name', '[class*="actress"]', '[class*="rank"]', 'h3', '.name']:
            elems = soup.select(sel)
            texts = [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]
            if texts:
                print(f'Selector {sel}: {texts[:10]}')

        await browser.close()

asyncio.run(test())
