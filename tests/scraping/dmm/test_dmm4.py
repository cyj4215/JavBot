with open('/tmp/dmm_rank2.html', 'r', encoding='utf-8') as f:
    html = f.read()

from bs4 import BeautifulSoup
soup = BeautifulSoup(html, 'html.parser')

# Check if body is mostly empty (SPA indicator)
body = soup.find('body')
if body:
    body_text = body.get_text(strip=True)
    print('Body text length:', len(body_text))
    print('Body text:', body_text[:500])

# Check for root div (React/Vue indicator)
divs = soup.find_all('div')
print('Number of divs:', len(divs))
for div in divs[:10]:
    div_id = div.get('id', '')
    div_class = ' '.join(div.get('class', [])) if div.get('class') else ''
    if div_id or div_class:
        print(f'Div: id={div_id}, class={div_class}')

# Check for script src
scripts = soup.find_all('script')
print('Number of scripts:', len(scripts))
for script in scripts:
    src = script.get('src', '')
    if src:
        print(f'Script src: {src[:100]}')
    elif script.string:
        text = script.string.strip()
        if 'ranking' in text.lower() or 'actress' in text.lower() or 'data' in text.lower():
            print(f'Script content: {text[:200]}')

# Check for JSON API endpoints
import re
api_matches = re.findall(r'(/api/[^"\'\s]+)', html)
if api_matches:
    print('API endpoints:', api_matches[:10])
