import sys, os
sys.path.insert(0, '/app')

from app.service import ActressService

proxy = os.environ.get('http_proxy', '')
svc = ActressService(proxy_addr=proxy, latest_limit=3)

# get_latest_works removed — JavDb endpoint disabled (Cloudflare).
# Tests 1 & 2 removed accordingly.
# This file kept for future JavDb re-integration testing.

# Test: Full query_profile (uses JavBus fallback)
print('\n=== 测试 query_profile (JavBus 回退) ===')
profile = svc.query_profile('河北彩伽')
print(f'   Found: {profile.found}')
print(f'   Latest works: {len(profile.latest_works or [])}')
for w in (profile.latest_works or [])[:3]:
    print(f'   - {w.get("id", "?")} | {w.get("date", "?")}')
