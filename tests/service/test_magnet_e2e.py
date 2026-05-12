import sys, os
sys.path.insert(0, '/app')

import asyncio
from app.secure_callback import short_callback, resolve_callback
from app.service import ActressService

# Test 1: Create a magnet callback and resolve it
print('=== 测试回调创建和解析 ===')
token = short_callback('magnet', 'SSIS-834')
print(f'Created token: {token}')

resolved = resolve_callback('magnet', token)
print(f'Resolved: {resolved}')

if resolved != 'SSIS-834':
    print('❌ 回调解析失败！')
else:
    print('✅ 回调解析成功')

print()

# Test 2: Full magnet search flow
print('=== 测试完整磁力搜索流程 ===')
proxy = os.environ.get('http_proxy', '')
svc = ActressService(proxy_addr=proxy)

# Get AV meta
print('Getting AV meta for SSIS-834...')
av_meta = svc._javbus_svc.get_av_meta('SSIS-834')
print(f'AV Meta: id={av_meta.get("id")}, title={av_meta.get("title", "")[:30]}...')

# Get magnets
print('Getting magnets...')
magnets = svc.get_av_magnets('SSIS-834', limit=3)
print(f'Found {len(magnets)} magnets')

if magnets:
    print('✅ 磁力搜索成功')
    for m in magnets[:2]:
        print(f'  - {m.get("magnet", "")[:50]}...')
else:
    print('❌ 未找到磁力')

print()

# Test 3: Test with a real profile query (simulating the button click flow)
print('=== 模拟按钮点击流程 ===')
profile = svc.query_profile('河北彩伽')
if profile.found and profile.latest_works:
    work = profile.latest_works[0]
    av_id = work.get('id', '')
    print(f'First work ID: {av_id}')
    
    # Create callback for this work
    token = short_callback('magnet', av_id)
    print(f'Created magnet callback for {av_id}')
    
    # Resolve it
    resolved = resolve_callback('magnet', token)
    print(f'Resolved to: {resolved}')
    
    # Search magnets
    magnets = svc.get_av_magnets(av_id, limit=3)
    print(f'Found {len(magnets)} magnets for {av_id}')
    if magnets:
        print('✅ 按钮点击流程正常')
    else:
        print('⚠️ 该作品暂无磁力')
else:
    print('❌ 未找到女优信息')
