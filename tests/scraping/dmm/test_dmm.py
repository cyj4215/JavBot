import requests
from bs4 import BeautifulSoup

url = 'https://www.dmm.co.jp/digital/videoa/-/ranking/=/type=actress/page=1/'
resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'Cookie': 'age_check_done=1'}, timeout=15)
print('Status:', resp.status_code)
html = resp.text
print('HTML length:', len(html))

soup = BeautifulSoup(html, 'html.parser')

# Try to find actress names in the new layout
for sel in ['.rank-name', '.actress-name', '[class*="actress"]', '[class*="rank"]', 'h3', '.c-rank__name', '.d-rank__name']:
    elems = soup.select(sel)
    texts = [e.get_text(strip=True) for e in elems if e.get_text(strip=True)]
    if texts:
        print(f'Selector {sel}: {texts[:10]}')

# Check all links with actress in href
links = soup.find_all('a', href=lambda x: x and 'actress' in x)
print('Actress links:', len(links))
for link in links[:10]:
    print('  -', link.get_text(strip=True), link.get('href', '')[:60])

# Check for JSON in script tags
scripts = soup.find_all('script')
for script in scripts:
    if script.string and 'actress' in script.string.lower():
        print('Script found with actress data')
        break

# Save HTML for inspection
with open('/tmp/dmm_rank.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Saved to /tmp/dmm_rank.html')
