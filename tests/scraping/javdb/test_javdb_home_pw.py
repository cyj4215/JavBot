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

        # Navigate to JavDb home
        url = 'https://javdb.com/'
        print(f'Navigating to {url}')
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(3)

        print(f'Current URL: {page.url}')

        html = await page.content()
        print(f'HTML length: {len(html)}')

        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('title')
        print('Title:', title.get_text() if title else 'No title')

        # Look for sections that might contain popular actresses
        sections = soup.find_all(['section', 'div', 'h2', 'h3'])
        for section in sections:
            text = section.get_text(strip=True)
            if text and ('热门' in text or '人気' in text or 'popular' in text.lower() or '排行' in text):
                print(f'Section: {text[:100]}')
                # Get next siblings
                next_elem = section.find_next_sibling()
                if next_elem:
                    print(f'  Next: {next_elem.get_text(strip=True)[:200]}')

        # Check all links for actress names (href containing actor)
        links = soup.find_all('a', href=lambda x: x and 'actor' in x)
        print(f'\nFound {len(links)} actor links')
        for link in links[:20]:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            print(f'  {text} -> {href}')

        # Check for any images with alt text that might be actress names
        imgs = soup.find_all('img')
        for img in imgs:
            alt = img.get('alt', '')
            if alt and len(alt) > 1 and len(alt) < 20:
                print(f'Img alt: {alt}')

        await browser.close()

asyncio.run(test())
