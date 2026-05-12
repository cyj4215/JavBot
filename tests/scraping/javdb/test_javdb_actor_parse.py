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

        url = 'https://javdb.com/actors'
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(3)

        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        # Find actor boxes and print their structure
        actor_boxes = soup.find_all(class_='actor-box')
        print(f'Found {len(actor_boxes)} actor boxes')

        for i, box in enumerate(actor_boxes[:3]):
            print(f'\n--- Box {i} ---')
            print(box.prettify()[:1000])

            # Try to extract name
            name_elem = box.find('strong') or box.find('span') or box.find('a')
            if name_elem:
                print(f'Name: {name_elem.get_text(strip=True)}')

            # Try to extract image
            img = box.find('img')
            if img:
                print(f'Image: {img.get("src", img.get("data-src", ""))}')

            # Try to extract link
            a = box.find('a')
            if a:
                print(f'Link: {a.get("href", "")}')

        await browser.close()

asyncio.run(test())
