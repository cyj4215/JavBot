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

        # Try different URLs
        urls = [
            'https://javdb.com/',
            'https://javdb.com/rankings/video',
            'https://javdb.com/rankings/actress',
        ]

        for url in urls:
            print(f'\n--- Testing {url} ---')
            try:
                await page.goto(url, wait_until='networkidle', timeout=20000)
                await asyncio.sleep(2)

                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.find('title')
                print('Title:', title.get_text() if title else 'No title')
                print('URL:', page.url)

                # Check for ranking links
                links = soup.find_all('a')
                for link in links:
                    text = link.get_text(strip=True)
                    href = link.get('href', '')
                    if 'rank' in href.lower() or '排行' in text:
                        print(f'Ranking link: {text} -> {href}')

            except Exception as e:
                print(f'Error: {e}')

        await browser.close()

asyncio.run(test())
