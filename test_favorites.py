#!/usr/bin/env python3
"""
测试收藏功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.favorites import FavoritesManager

def test_favorites():
    """测试收藏管理器"""
    print("测试收藏功能...")
    
    # 使用内存数据库进行测试
    manager = FavoritesManager(":memory:")
    
    # 测试添加用户
    manager._ensure_user(12345, "test_user", "Test", "User")
    print("✓ 用户添加成功")
    
    # 测试添加收藏
    success = manager.add_favorite(
        user_id=12345,
        actress_name="三上悠亜",
        actress_id="mikami-yua",
        actress_data={"star_name": "三上悠亜", "star_id": "mikami-yua"}
    )
    print(f"✓ 添加收藏: {success}")
    
    # 测试检查收藏状态
    is_fav = manager.is_favorite(12345, "三上悠亜")
    print(f"✓ 检查收藏状态: {is_fav}")
    
    # 测试获取收藏列表
    favorites = manager.get_favorites(12345)
    print(f"✓ 获取收藏列表: {len(favorites)} 个收藏")
    for fav in favorites:
        print(f"  - {fav['actress_name']} (ID: {fav['actress_id']})")
    
    # 测试获取收藏数量
    count = manager.get_favorite_count(12345)
    print(f"✓ 收藏数量: {count}")
    
    # 测试记录查询历史
    manager.record_favorite_query(12345, "三上悠亜")
    print("✓ 记录查询历史成功")
    
    # 测试获取查询记录
    queries = manager.get_recent_favorite_queries(12345)
    print(f"✓ 最近查询记录: {len(queries)} 条")
    
    # 测试移除收藏
    success = manager.remove_favorite(12345, "三上悠亜")
    print(f"✓ 移除收藏: {success}")
    
    # 验证已移除
    is_fav = manager.is_favorite(12345, "三上悠亜")
    print(f"✓ 检查收藏状态（移除后）: {is_fav}")
    
    print("\n所有测试通过！")

if __name__ == "__main__":
    test_favorites()