import sys, os
sys.path.insert(0, '/app')

from app.service import ActressService

proxy = os.environ.get('http_proxy', '')
svc = ActressService(proxy_addr=proxy)

# Test magnet search
print('=== 测试搜索磁力 ===')
magnets = svc.get_av_magnets('SSIS-834', limit=3)
print(f'Found {len(magnets)} magnets for SSIS-834')
for m in magnets[:3]:
    print(f'  - {m.get("magnet", "?")[:60]}...')
    print(f'    Size: {m.get("size", "?")}, Date: {m.get("date", "?")}')

print()

# Test another
print('=== 测试另一个番号磁力 ===')
magnets2 = svc.get_av_magnets('IPX-416', limit=3)
print(f'Found {len(magnets2)} magnets for IPX-416')
for m in magnets2[:3]:
    print(f'  - {m.get("magnet", "?")[:60]}...')
    print(f'    Size: {m.get("size", "?")}, Date: {m.get("date", "?")}')
