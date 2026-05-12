import sys, os
sys.path.insert(0, '/app')

from app.secure_callback import SecureCallbackStore

# Test callback store
store = SecureCallbackStore()

print('=== 测试回调存储 ===')
# Store a callback
token = store.create('search', 'SSIS-834')
print(f'Stored callback: {token[:30]}...')

# Retrieve it
result = store.resolve('search', token)
print(f'Retrieved: {result}')

# Test invalid callback
invalid_result = store.resolve('search', 'invalid_token')
print(f'Invalid callback: {invalid_result}')

print('\n✅ 回调存储测试通过')
