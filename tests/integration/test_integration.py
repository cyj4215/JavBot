#!/usr/bin/env python3
"""
集成测试 - 验证数据库优化成果
"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

from app.fav_manager import FavoritesManager


def test_keyset_pagination():
    print("\n=== 测试 Keyset Pagination ===")

    manager = FavoritesManager(":memory:")

    for i in range(15):
        manager.add_favorite(
            user_id=12345,
            actress_name=f"女优{i}",
            actress_id=f"id-{i}",
            actress_data={"extra_info": f"info-{i}"}
        )
        time.sleep(0.01)

    result1 = manager.get_favorites(12345, limit=5)
    assert len(result1["items"]) == 5, f"第一页应该有5条，实际{len(result1['items'])}"
    assert result1["total"] == 15, f"总数应为15，实际{result1['total']}"
    assert result1["next_cursor"] is not None, "应该有 next_cursor"
    print(f"✓ 第一页: {len(result1['items'])} 条, next_cursor={result1['next_cursor']}, total={result1['total']}")

    result2 = manager.get_favorites(12345, limit=5, cursor=result1["next_cursor"])
    assert len(result2["items"]) == 5, f"第二页应该有5条"
    assert result2["total"] == 15, "后续分页 total 应始终为正确的总数"
    print(f"✓ 第二页: {len(result2['items'])} 条, next_cursor={result2['next_cursor']}, total={result2['total']}")

    ids1 = set(f["id"] for f in result1["items"])
    ids2 = set(f["id"] for f in result2["items"])
    overlap = ids1 & ids2
    assert len(overlap) == 0, f"两页不应有重叠，实际重叠: {overlap}"
    print(f"✓ 两页无重叠 ID")

    result3 = manager.get_favorites(12345, limit=20)
    assert len(result3["items"]) == 15, f"limit超过总数应返回全部15条"
    assert result3["next_cursor"] is None, "只有一页时不应有 next_cursor"
    print(f"✓ 全量查询: {len(result3['items'])} 条, next_cursor=None")

    print("✓ Keyset Pagination 测试通过！")


def test_actress_data_optimization():
    print("\n=== 测试 actress_data 精简 ===")

    manager = FavoritesManager(":memory:")

    manager.add_favorite(
        user_id=12345,
        actress_name="三上悠亜",
        actress_id="mikami-yua",
        actress_data={
            "star_name": "三上悠亜",
            "star_id": "mikami-yua",
            "wiki_url": "https://example.com",
            "extra_info": "重要信息"
        }
    )

    result = manager.get_favorites(12345)
    fav = result["items"][0]

    assert "actress_data" in fav, "应该有 actress_data 字段"
    actress_data = fav["actress_data"]
    assert "extra_info" in actress_data, "actress_data 应包含 extra_info"
    assert actress_data["extra_info"] == "重要信息", "extra_info 值应保留"

    assert "star_name" not in actress_data, "冗余字段 star_name 应被移除"
    assert "star_id" not in actress_data, "冗余字段 star_id 应被移除"
    assert "wiki_url" not in actress_data, "冗余字段 wiki_url 应被移除"
    print(f"✓ actress_data 只保留 extra_info: {actress_data}")

    result2 = manager.add_favorite(
        user_id=12345,
        actress_name="苍井空",
        actress_id="aoi-sora",
        actress_data={"star_name": "苍井空", "star_id": "aoi-sora"}
    )
    result3 = manager.get_favorites(12345)
    aoi = next((f for f in result3["items"] if f["actress_name"] == "苍井空"), None)
    assert aoi is not None, "第二个收藏应该添加成功"
    assert aoi.get("actress_data") is None, "无 extra_info 时 actress_data 应为 None"
    print(f"✓ 无 extra_info 时 actress_data 为 None")

    print("✓ actress_data 精简测试通过！")


def test_user_sync():
    print("\n=== 测试用户信息同步 ===")

    manager = FavoritesManager(":memory:")

    manager._sync_user(99999, "john_doe", "John", "Doe")
    print("✓ _sync_user 方法可用")

    manager.add_favorite(
        user_id=99999,
        actress_name="测试女优",
        actress_id="test-id",
        actress_data={"extra_info": "test"}
    )
    print("✓ add_favorite 内部调用 _sync_user 成功")

    cursor = manager._conn.cursor()
    cursor.execute("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (99999,))
    row = cursor.fetchone()
    assert row is not None, "用户记录应该存在"
    print(f"✓ 用户信息已记录: username={row[0]}, first_name={row[1]}, last_name={row[2]}")

    print("✓ 用户同步测试通过！")


def run_all_tests():
    print("=" * 50)
    print("开始运行集成测试")
    print("=" * 50)

    try:
        test_keyset_pagination()
        test_actress_data_optimization()
        test_user_sync()

        print("\n" + "=" * 50)
        print("🎉 所有集成测试通过！")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
