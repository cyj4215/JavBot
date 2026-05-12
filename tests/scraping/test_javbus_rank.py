import requests
from bs4 import BeautifulSoup

# Try JavBus actress page
url = 'https://www.javbus.com/actresses'
resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
print('Status:', resp.status_code)

soup = BeautifulSoup(resp.text, 'html.parser')
title = soup.find('title')
print('Title:', title.get_text() if title else 'No title')

# Check all links with actress names
links = soup.find_all('a')
count = 0
for link in links:
    text = link.get_text(strip=True)
    href = link.get('href', '')
    if text and len(text) > 1 and len(text) < 20 and ('star' in href or 'actress' in href):
        print(f'Link: {text} -> {href[:60]}')
        count += 1
        if count >= 20:
            break

# Check for star items
for sel in ['.star-box', '.actress-box', '[class*="star"]', '.item', '.avatar-box']:
    elems = soup.select(sel)
    texts = [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]
    if texts:
        print(f'Selector {sel}: {len(elems)} items, first 3: {texts[:3]}')
