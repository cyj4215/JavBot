#!/usr/bin/env python3
"""
简单测试收藏功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.favorites import FavoritesManager

def test_simple():
    """简单测试"""
    print("简单测试收藏功能...")
    
    try:
        # 使用文件数据库进行测试
        test_db = "/tmp/test_favorites.db"
        if os.path.exists(test_db):
            os.remove(test_db)
            
        manager = FavoritesManager(test_db)
        print("✓ 管理器初始化成功")
        
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
        
        print("\n所有测试通过！")
        
        # 清理
        os.remove(test_db)
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple()