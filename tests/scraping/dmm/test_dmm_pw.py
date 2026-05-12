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

        # Go to DMM ranking page
        url = 'https://www.dmm.co.jp/digital/videoa/-/ranking/=/type=actress/page=1/'
        print(f'Navigating to {url}')
        await page.goto(url, wait_until='networkidle', timeout=30000)

        # Check for age verification
        current_url = page.url
        print(f'Current URL: {current_url}')

        # If on age check page, click agree
        if 'age_check' in current_url:
            print('Age check detected, looking for agree button...')
            # Try to find and click agree button
            agree_btn = await page.query_selector('a:has-text("はい")') or \
                       await page.query_selector('a:has-text("I Agree")') or \
                       await page.query_selector('button:has-text("はい")')
            if agree_btn:
                await agree_btn.click()
                await page.wait_for_load_state('networkidle')
                print(f'After click URL: {page.url}')

        # Wait for content to load
        await asyncio.sleep(3)

        # Get page content
        html = await page.content()
        print(f'HTML length: {len(html)}')

        # Try to find actress names
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Check title
        title = soup.find('title')
        print('Title:', title.get_text() if title else 'No title')

        # Various selectors
        for sel in ['.rank-name', '.actress-name', '[class*="actress"]', '[class*="rank"]', 'h3', '.name']:
            elems = soup.select(sel)
            texts = [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]
            if texts:
                print(f'Selector {sel}: {texts[:10]}')

        # Check all links
        links = soup.find_all('a')
        for link in links:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            if text and len(text) > 1 and len(text) < 20 and ('actress' in href or 'actor' in href):
                print(f'Link: {text} -> {href[:60]}')

        await browser.close()

asyncio.run(test())
