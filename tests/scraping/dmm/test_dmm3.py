with open('/tmp/dmm_rank2.html', 'r', encoding='utf-8') as f:
    html = f.read()

from bs4 import BeautifulSoup
soup = BeautifulSoup(html, 'html.parser')

# Check title
title = soup.find('title')
print('Title:', title.get_text() if title else 'No title')

# Try various selectors for actress names
for sel in ['.rank-name', '.actress-name', '[class*="actress"]', '[class*="rank"]', 'h3', '.c-rank__name', '.d-rank__name', '.name']:
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

# Check JSON data in scripts
import re
scripts = soup.find_all('script')
for script in scripts:
    if script.string and ('actress' in script.string.lower() or 'name' in script.string.lower()):
        matches = re.findall(r'"name":"([^"]{2,20})"', script.string)
        if matches:
            print('JSON names:', matches[:20])
            break
