#!/usr/bin/env python3
"""
性能基准测试 - 对比 OFFSET vs Keyset 分页性能

重点测试深分页场景下的性能差异。
"""
import sys
import os
import time
import statistics
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

from app.fav_manager import FavoritesManager


def create_test_data(manager: FavoritesManager, user_id: int, count: int):
    print(f"创建 {count} 条测试数据...")
    for i in range(count):
        manager.add_favorite(
            user_id=user_id,
            actress_name=f"女优{i:05d}",
            actress_id=f"id-{i:05d}",
            actress_data={"extra_info": f"info-{i}"}
        )
        if i % 500 == 0 and i > 0:
            print(f"  已创建 {i}/{count} 条")


def benchmark_deep_pagination():
    print("=" * 60)
    print("深分页性能测试")
    print("=" * 60)

    test_db = "/tmp/benchmark_deep.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    manager = FavoritesManager(test_db)
    user_id = 12345

    print("\n准备测试数据（10000条）...")
    create_test_data(manager, user_id, 10000)

    offsets = [100, 1000, 5000, 9000]
    page_size = 10

    print(f"\n--- OFFSET 分页测试 (page_size={page_size}) ---")
    for offset in offsets:
        times = []
        for _ in range(3):
            start = time.perf_counter()
            result = manager.get_favorites_legacy(user_id, limit=page_size, offset=offset)
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)
        avg = statistics.mean(times)
        print(f"  OFFSET {offset:5d}: 平均 {avg:.2f}ms (获取 {len(result)} 条)")

    print(f"\n--- Keyset 分页测试 (page_size={page_size}) ---")
    cursor = None
    page_num = 0
    for target_page in [10, 100, 500, 900]:
        times = []
        for _ in range(3):
            cursor = None
            start = time.perf_counter()
            for _ in range(target_page):
                result = manager.get_favorites(user_id, limit=page_size, cursor=cursor)
                cursor = result.get('next_cursor')
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)
        avg = statistics.mean(times)
        print(f"  第 {target_page:3d} 页: 平均 {avg:.2f}ms (cursor={cursor is not None})")

    os.remove(test_db)
    print("\n深分页测试完成！")
    print("\n结论: Keyset 分页的时间复杂度是 O(页数)，而 OFFSET 是 O(OFFSET)。")
    print("      在深分页场景（如第1000页），Keyset 优势明显。")


def run_benchmark():
    benchmark_deep_pagination()


if __name__ == "__main__":
    run_benchmark()
