import requests
from bs4 import BeautifulSoup

# Try DMM mobile version
urls = [
    'https://www.dmm.co.jp/digital/videoa/-/ranking/=/type=actress/page=1/',
    'https://sp.dmm.co.jp/digital/videoa/-/ranking/=/type=actress/page=1/',
    'https://m.dmm.co.jp/digital/videoa/-/ranking/=/type=actress/page=1/',
    'https://www.dmm.com/digital/videoa/-/ranking/=/type=actress/page=1/',
]

for url in urls:
    print(f'\n--- Testing {url} ---')
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'})

        # First age check
        age_url = f'https://www.dmm.co.jp/age_check/=/declared=yes/?rurl={url.replace("https://", "").replace("/", "%2F")}'
        session.get(age_url, timeout=10)

        resp = session.get(url, timeout=10)
        print('Status:', resp.status_code)
        print('URL:', resp.url)

        soup = BeautifulSoup(resp.text, 'html.parser')
        data_items = soup.find_all(class_='data')
        print('Data items:', len(data_items))

        if data_items:
            for item in data_items[:3]:
                print('  -', item.get_text(strip=True)[:50])
        else:
            title = soup.find('title')
            print('Title:', title.get_text() if title else 'No title')

    except Exception as e:
        print(f'Error: {e}')
