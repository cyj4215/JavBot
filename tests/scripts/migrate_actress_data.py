#!/usr/bin/env python3
"""
数据迁移脚本 - 清理冗余的 actress_data 字段

此脚本将所有 favorites 表中的 actress_data 字段精简为只保留 extra_info。
迁移前备份数据库，迁移过程支持事务回滚。

用法:
    python migrate_actress_data.py [--dry-run] [--backup-dir DIR]

示例:
    # 预览迁移（不实际修改）
    python migrate_actress_data.py --dry-run

    # 执行迁移
    python migrate_actress_data.py

    # 指定备份目录
    python migrate_actress_data.py --backup-dir /tmp/backups
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def get_db_path() -> str:
    db_path = os.getenv("FAVORITES_DB_PATH")
    if not db_path:
        home_dir = Path.home()
        db_path = str(home_dir / ".openclaw" / "javbot_favorites.db")
    return db_path


def backup_database(db_path: str, backup_dir: str) -> str:
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"javbot_favorites_backup_{timestamp}.db")

    shutil.copy2(db_path, backup_path)
    print(f"✓ 数据库已备份至: {backup_path}")
    return backup_path


def migrate_actress_data(db_path: str, dry_run: bool = True) -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM favorites")
    total_count = cursor.fetchone()[0]

    cursor.execute("SELECT id, actress_data FROM favorites WHERE actress_data IS NOT NULL")
    rows = cursor.fetchall()

    updated_count = 0
    skipped_count = 0
    errors = []

    for row_id, actress_data_json in rows:
        try:
            data = json.loads(actress_data_json)

            if not isinstance(data, dict):
                skipped_count += 1
                continue

            if 'extra_info' in data:
                original_keys = list(data.keys())
                extra_info = data.get('extra_info')
                new_data = {'extra_info': extra_info} if extra_info else None

                if dry_run:
                    print(f"  [DRY-RUN] ID {row_id}: {original_keys} -> {list(new_data.keys()) if new_data else 'None'}")
                else:
                    new_data_json = json.dumps(new_data, ensure_ascii=False) if new_data else None
                    cursor.execute(
                        "UPDATE favorites SET actress_data = ? WHERE id = ?",
                        (new_data_json, row_id)
                    )
                    updated_count += 1
            else:
                if dry_run:
                    print(f"  [SKIP] ID {row_id}: 无 extra_info 字段，保持不变")
                skipped_count += 1

        except json.JSONDecodeError as e:
            errors.append(f"ID {row_id}: JSON 解析失败 - {e}")
            skipped_count += 1
        except Exception as e:
            errors.append(f"ID {row_id}: {e}")
            skipped_count += 1

    if not dry_run:
        conn.commit()
        print(f"✓ 已更新 {updated_count} 条记录")

    conn.close()

    return {
        'total': total_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'errors': errors
    }


def main():
    parser = argparse.ArgumentParser(description="迁移 actress_data 字段，精简为只保留 extra_info")
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际修改数据')
    parser.add_argument('--backup-dir', default='/tmp/javbot_backups', help='备份目录')
    args = parser.parse_args()

    db_path = get_db_path()

    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)

    print(f"数据库路径: {db_path}")
    print(f"模式: {'预览' if args.dry_run else '执行'}")
    print()

    backup_path = backup_database(db_path, args.backup_dir)

    print()
    print("开始迁移...")
    print("-" * 50)

    result = migrate_actress_data(db_path, dry_run=args.dry_run)

    print("-" * 50)
    print(f"总记录数: {result['total']}")
    print(f"将更新: {result['updated']}")
    print(f"跳过: {result['skipped']}")

    if result['errors']:
        print(f"错误数: {len(result['errors'])}")
        for err in result['errors'][:10]:
            print(f"  - {err}")
        if len(result['errors']) > 10:
            print(f"  ... 还有 {len(result['errors']) - 10} 个错误")

    if args.dry_run:
        print()
        print("这是预览模式，未实际修改数据。")
        print("如需执行迁移，请运行: python migrate_actress_data.py")
    else:
        print()
        print("迁移完成！")
        print(f"备份文件: {backup_path}")


if __name__ == "__main__":
    main()
