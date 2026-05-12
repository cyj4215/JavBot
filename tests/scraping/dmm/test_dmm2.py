import requests
from bs4 import BeautifulSoup

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

# Visit the age check page with declared=yes
age_url = 'https://www.dmm.co.jp/age_check/=/declared=yes/?rurl=https%3A%2F%2Fwww.dmm.co.jp%2Fdigital%2Fvideoa%2F-%2Franking%2F%3D%2Ftype%3Dactress%2Fpage%3D1%2F'
resp = session.get(age_url, timeout=15)
print('Age check status:', resp.status_code)
print('Cookies:', session.cookies.get_dict())

# Now try the ranking page
rank_url = 'https://www.dmm.co.jp/digital/videoa/-/ranking/=/type=actress/page=1/'
resp2 = session.get(rank_url, timeout=15)
print('Rank status:', resp2.status_code)
print('Rank URL:', resp2.url)

soup = BeautifulSoup(resp2.text, 'html.parser')
data_items = soup.find_all(class_='data')
print('Data items:', len(data_items))
if data_items:
    for item in data_items[:5]:
        print('  -', item.get_text(strip=True)[:50])
else:
    title = soup.find('title')
    print('Title:', title.get_text() if title else 'No title')
    print('HTML length:', len(resp2.text))
    # Save for inspection
    with open('/tmp/dmm_rank2.html', 'w', encoding='utf-8') as f:
        f.write(resp2.text)
    print('Saved to /tmp/dmm_rank2.html')
