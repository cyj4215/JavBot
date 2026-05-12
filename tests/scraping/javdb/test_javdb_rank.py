import requests
from bs4 import BeautifulSoup

# Try JavDb actress ranking
url = 'https://javdb.com/rankings'
resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
print('Status:', resp.status_code)
print('URL:', resp.url)

soup = BeautifulSoup(resp.text, 'html.parser')
title = soup.find('title')
print('Title:', title.get_text() if title else 'No title')

# Look for actress names
links = soup.find_all('a')
for link in links:
    text = link.get_text(strip=True)
    href = link.get('href', '')
    if text and len(text) > 1 and len(text) < 20 and ('actor' in href or 'actress' in href):
        print(f'Link: {text} -> {href[:60]}')

# Check for rank items
for sel in ['.rank-item', '.ranking-item', '[class*="rank"]', '.item']:
    elems = soup.select(sel)
    texts = [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]
    if texts:
        print(f'Selector {sel}: {texts[:5]}')

print('---')
# Also try JavBus
url2 = 'https://www.javbus.com/actresses'
resp2 = requests.get(url2, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
print('JavBus Status:', resp2.status_code)

soup2 = BeautifulSoup(resp2.text, 'html.parser')
for sel in ['.star-box', '.actress-box', '[class*="star"]', '.item']:
    elems = soup2.select(sel)
    texts = [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]
    if texts:
        print(f'JavBus Selector {sel}: {texts[:5]}')
