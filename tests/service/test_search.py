import sys, os
sys.path.insert(0, '/app')

from app.service import ActressService

proxy = os.environ.get('http_proxy', '')
svc = ActressService(proxy_addr=proxy, latest_limit=3, top_limit=3)

# Test 1: Search for a popular actress
print('=== 测试 /search 搜索女优 ===')
profile = svc.query_profile('河北彩伽')
print(f'Query: 河北彩伽')
print(f'Found: {profile.found}')
if profile.found:
    print(f'Star Name: {profile.star_name}')
    print(f'Latest works: {len(profile.latest_works or [])}')
    for w in (profile.latest_works or [])[:3]:
        print(f'  - {w.get("id", "?")} | {w.get("date", "?")}')
else:
    print(f'Suggestions: {profile.suggestions[:5] if profile.suggestions else "None"}')

print()

# Test 2: Another actress
print('=== 测试另一位女优 ===')
profile2 = svc.query_profile('三上悠亜')
print(f'Query: 三上悠亜')
print(f'Found: {profile2.found}')
if profile2.found:
    print(f'Star Name: {profile2.star_name}')
    print(f'Latest works: {len(profile2.latest_works or [])}')
    for w in (profile2.latest_works or [])[:3]:
        print(f'  - {w.get("id", "?")} | {w.get("date", "?")}')
