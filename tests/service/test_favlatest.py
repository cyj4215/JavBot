import sys, os
sys.path.insert(0, '/app')

from app.fav_manager import FavoritesManager
from app.service import ActressService

# Setup
db_path = os.environ.get('FAVORITES_DB_PATH', '/app/data/favorites.db')
db = FavoritesManager(db_path)
proxy = os.environ.get('http_proxy', '')
svc = ActressService(proxy_addr=proxy, latest_limit=3)

# Add test favorites
print('=== 准备测试数据 ===')
db.add_favorite(12345, '河北彩花')
db.add_favorite(12345, '三上悠亜')
print('Added 2 test favorites')

# Test favlatest logic
print('\n=== 测试 /favlatest 逻辑 ===')
favs = db.get_favorites(12345)
print(f'Total favorites: {favs["total"]}')

for item in favs['items'][:2]:
    name = item['actress_name']
    print(f'\nFetching latest for: {name}')
    profile = svc.query_profile(name)
    if profile.found and profile.latest_works:
        print(f'  Found {len(profile.latest_works)} works')
        for w in profile.latest_works[:2]:
            print(f'    - {w.get("id", "?")} | {w.get("date", "?")}')
    else:
        print(f'  No works found')

# Cleanup
for item in db.get_favorites(12345)['items']:
    db.remove_favorite(12345, item['actress_name'])
print('\nCleanup done')
