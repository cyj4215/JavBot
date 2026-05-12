import requests
from bs4 import BeautifulSoup

url = 'https://www.javbus.com/star/okq'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
resp = requests.get(url, headers=headers, timeout=10)
print('Status:', resp.status_code)
soup = BeautifulSoup(resp.text, 'lxml')
print('Soup title:', soup.title.string if soup.title else 'No title')
# 查找头像图片
img_tag = soup.find('img', class_='star-img')
print('Avatar img tag:', img_tag)
if img_tag:
    print('Avatar src:', img_tag.get('src'))
imgs = soup.find_all('img')
print('All imgs count:', len(imgs))
for img in imgs[:10]:
    print('Img class:', img.get('class'), 'src:', img.get('src'))
