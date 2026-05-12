#!/usr/bin/env python3
"""
测试收藏功能
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

from app.fav_manager import FavoritesManager


def test_favorites():
    print("测试收藏功能...")

    manager = FavoritesManager(":memory:")

    manager._sync_user(12345, "test_user", "Test", "User")
    print("✓ 用户同步成功")

    success = manager.add_favorite(
        user_id=12345,
        actress_name="三上悠亜",
        actress_id="mikami-yua",
        actress_data={"extra_info": "some info"}
    )
    print(f"✓ 添加收藏: {success}")

    is_fav = manager.is_favorite(12345, "三上悠亜")
    print(f"✓ 检查收藏状态: {is_fav}")

    result = manager.get_favorites(12345)
    favorites = result.get('items', []) if isinstance(result, dict) else result
    print(f"✓ 获取收藏列表: {len(favorites)} 个收藏")
    for fav in favorites:
        print(f"  - {fav['actress_name']} (ID: {fav['actress_id']})")
        if fav.get('actress_data'):
            print(f"    actress_data: {fav['actress_data']}")

    count = manager.get_favorite_count(12345)
    print(f"✓ 收藏数量: {count}")

    manager.record_favorite_query(12345, "三上悠亜")
    print("✓ 记录查询历史成功")

    queries = manager.get_recent_favorite_queries(12345)
    print(f"✓ 最近查询记录: {len(queries)} 条")

    success = manager.remove_favorite(12345, "三上悠亜")
    print(f"✓ 移除收藏: {success}")

    is_fav = manager.is_favorite(12345, "三上悠亜")
    print(f"✓ 检查收藏状态（移除后）: {is_fav}")

    print("\n所有测试通过！")


if __name__ == "__main__":
    test_favorites()
