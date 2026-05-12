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

        # Navigate to JavDb actors page
        url = 'https://javdb.com/actors'
        print(f'Navigating to {url}')
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(3)

        print(f'Current URL: {page.url}')

        html = await page.content()
        print(f'HTML length: {len(html)}')

        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('title')
        print('Title:', title.get_text() if title else 'No title')

        # Look for actor items
        for sel in ['.actor-item', '.actor-box', '[class*="actor"]', '.item', '.card']:
            elems = soup.select(sel)
            texts = [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]
            if texts:
                print(f'Selector {sel}: {len(elems)} items, first 5: {texts[:5]}')

        # Check all links for actor names
        links = soup.find_all('a', href=lambda x: x and 'actor' in x)
        print(f'\nFound {len(links)} actor links')
        for link in links[:20]:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            if text and len(text) > 1 and len(text) < 20:
                print(f'  {text} -> {href}')

        await browser.close()

asyncio.run(test())
