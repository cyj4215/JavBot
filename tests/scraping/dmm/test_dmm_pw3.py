import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            locale='ja-JP',
        )
        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)

        # Try accessing the new DMM ranking URL directly
        url = 'https://video.dmm.co.jp/av/ranking/?term=monthly&type=actress'
        print(f'Navigating to {url}')
        await page.goto(url, wait_until='networkidle', timeout=30000)

        print(f'Current URL: {page.url}')

        # Check if we're on age check page
        if 'age_check' in page.url:
            print('On age check page, looking for agree button...')
            # Try various selectors for agree button
            selectors = [
                'a:has-text("はい")',
                'a:has-text("同意する")',
                'button:has-text("はい")',
                'a[href*="declared=yes"]',
            ]
            for sel in selectors:
                btn = await page.query_selector(sel)
                if btn:
                    print(f'Found button with selector: {sel}')
                    await btn.click()
                    await page.wait_for_load_state('networkidle')
                    print(f'After click URL: {page.url}')
                    break

        # Wait for page to settle
        await asyncio.sleep(5)

        html = await page.content()
        print(f'HTML length: {len(html)}')

        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('title')
        print('Title:', title.get_text() if title else 'No title')

        # Look for ranking content
        for sel in ['[class*="ranking"]', '[class*="actress"]', 'h3', '.name', '[class*="item"]', '[class*="card"]']:
            elems = soup.select(sel)
            texts = [e.get_text(strip=True) for e in elems if e.get_text(strip=True) and len(e.get_text(strip=True)) < 30]
            if texts:
                print(f'Selector {sel}: {texts[:10]}')

        # Look for specific text patterns
        if 'ログイン' in html:
            print('LOGIN REQUIRED')
        if 'ランキング' in html:
            print('Has ranking text')

        # Check all links for actress names
        links = soup.find_all('a')
        for link in links:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            if text and len(text) > 1 and len(text) < 20 and ('actress' in href or 'actor' in href):
                print(f'Actress link: {text} -> {href[:60]}')

        await browser.close()

asyncio.run(test())
