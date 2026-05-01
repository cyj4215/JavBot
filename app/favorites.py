"""
收藏功能模块 - 用于存储和管理用户收藏的女优
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

QUERY_FREQUENCY_LIMIT = 10
QUERY_FREQUENCY_WINDOW = 3600


class FavoritesManager:

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.getenv("FAVORITES_DB_PATH")
            if not db_path:
                home_dir = Path.home()
                db_path = str(home_dir / ".openclaw" / "javbot_favorites.db")

        self.db_path = db_path
        self._lock = threading.Lock()
        logger.info(f"初始化收藏管理器，数据库路径: {self.db_path}")
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
        atexit.register(self.close)
        logger.info("收藏管理器初始化完成")

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _init_db(self):
        logger.debug(f"开始初始化数据库，路径: {self.db_path}")

        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

        cursor = self._conn.cursor()

        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                actress_name TEXT NOT NULL,
                actress_id TEXT,
                actress_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, actress_name)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorite_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                actress_name TEXT NOT NULL,
                query_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actress_works (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actress_name TEXT NOT NULL,
                av_id TEXT NOT NULL,
                title TEXT,
                date TEXT,
                url TEXT,
                img TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(actress_name, av_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_push_settings (
                user_id INTEGER PRIMARY KEY,
                push_enabled BOOLEAN DEFAULT 1,
                last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user_name ON favorites(user_id, actress_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorite_queries_user ON favorite_queries(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorite_queries_time ON favorite_queries(query_time)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_favorite_queries_user_actress '
            'ON favorite_queries(user_id, actress_name, query_time)'
        )
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actress_works_name ON actress_works(actress_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actress_works_name_id ON actress_works(actress_name, av_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actress_works_date ON actress_works(date DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_push_last_check ON user_push_settings(last_check)')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_push_enabled
            ON user_push_settings(user_id)
            WHERE push_enabled = 1
        ''')

        self._conn.commit()
        self.cleanup_old_data()

    @contextmanager
    def _transaction(self):
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _is_query_rate_limited(self, user_id: int, actress_name: str) -> bool:
        with self._lock:
            cursor = self._conn.cursor()
            window_start = (datetime.now() - timedelta(seconds=QUERY_FREQUENCY_WINDOW)).isoformat()
            cursor.execute(
                '''
                SELECT COUNT(*) FROM favorite_queries
                WHERE user_id = ? AND actress_name = ? AND query_time > ?
                ''',
                (user_id, actress_name, window_start)
            )
            count = cursor.fetchone()[0]
            return count >= QUERY_FREQUENCY_LIMIT

    def _upsert_favorite(
        self,
        user_id: int,
        actress_name: str,
        actress_id: str | None = None,
        actress_data: dict | None = None,
    ) -> bool:
        actress_data_json = json.dumps(actress_data, ensure_ascii=False) if actress_data else None
        cursor = self._conn.cursor()
        existing = cursor.execute(
            'SELECT id FROM favorites WHERE user_id = ? AND actress_name = ?',
            (user_id, actress_name)
        ).fetchone()
        if existing:
            cursor.execute(
                '''
                UPDATE favorites
                SET actress_id = COALESCE(?, actress_id),
                    actress_data = COALESCE(?, actress_data)
                WHERE user_id = ? AND actress_name = ?
                ''',
                (actress_id, actress_data_json, user_id, actress_name)
            )
        else:
            cursor.execute(
                '''
                INSERT INTO favorites (user_id, actress_name, actress_id, actress_data)
                VALUES (?, ?, ?, ?)
                ''',
                (user_id, actress_name, actress_id, actress_data_json)
            )
        return True

    def sync_user(self, user_id: int, username: str | None = None, first_name: str | None = None, last_name: str | None = None) -> bool:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO users (user_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username = excluded.username,
                        first_name = excluded.first_name,
                        last_name = excluded.last_name
                    WHERE excluded.username IS NOT NULL
                        OR excluded.first_name IS NOT NULL
                        OR excluded.last_name IS NOT NULL
                    ''',
                    (user_id, username, first_name, last_name)
                )
                self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"同步用户信息失败: {e}")
            return False

    def add_favorite(self, user_id: int, actress_name: str, actress_id: str | None = None, actress_data: dict | None = None) -> bool:
        try:
            self.sync_user(user_id)
            extra_only = {'extra_info': actress_data.get('extra_info')} if actress_data and actress_data.get('extra_info') else None
            with self._transaction():
                self._upsert_favorite(user_id, actress_name, actress_id, extra_only)
            return True
        except Exception as e:
            logger.error(f"添加收藏失败: {e}")
            return False

    def remove_favorite(self, user_id: int, actress_name: str) -> bool:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    'DELETE FROM favorites WHERE user_id = ? AND actress_name = ?',
                    (user_id, actress_name)
                )
                self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"移除收藏失败: {e}")
            return False

    def get_favorites(
        self,
        user_id: int,
        limit: int = 10,
        cursor: tuple[str, float] | None = None,
    ) -> dict[str, Any]:
        try:
            if cursor is not None:
                created_at_val, row_id_val = cursor
                where_clause = "WHERE user_id = ? AND (created_at < ? OR (created_at = ? AND id < ?))"
                where_params: tuple[Any, ...] = (user_id, created_at_val, created_at_val, row_id_val)
                count_c = self._conn.cursor()
                count_c.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,))
                total = count_c.fetchone()[0]
            else:
                where_clause = "WHERE user_id = ?"
                where_params = (user_id,)
                count_c = self._conn.cursor()
                count_c.execute(f"SELECT COUNT(*) FROM favorites {where_clause}", where_params)
                total = count_c.fetchone()[0]

            cur = self._conn.cursor()
            cur.execute(
                f"""
                SELECT id, actress_name, actress_id, actress_data, created_at
                FROM favorites
                {where_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (*where_params, limit)
            )
            rows = cur.fetchall()

            favorites = []
            for row in rows:
                favorite = {
                    'id': row[0],
                    'actress_name': row[1],
                    'actress_id': row[2],
                    'created_at': row[4],
                }
                if row[3]:
                    try:
                        favorite['actress_data'] = json.loads(row[3])
                    except Exception:
                        logger.debug("解析收藏数据 JSON 失败", exc_info=True)
                        favorite['actress_data'] = None
                favorites.append(favorite)

            next_cursor: tuple[str, float] | None = None
            if len(favorites) == limit and favorites:
                last = favorites[-1]
                next_cursor = (last['created_at'], last['id'])

            return {
                'items': favorites,
                'next_cursor': next_cursor,
                'total': total,
            }
        except Exception as e:
            logger.error(f"获取收藏列表失败: {e}")
            return {'items': [], 'next_cursor': None, 'total': 0}

    def is_favorite(self, user_id: int, actress_name: str) -> bool:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM favorites WHERE user_id = ? AND actress_name = ?',
                    (user_id, actress_name)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查收藏状态失败: {e}")
            return False

    def get_favorite_count(self, user_id: int) -> int:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    'SELECT COUNT(*) FROM favorites WHERE user_id = ?',
                    (user_id,)
                )
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"获取收藏数量失败: {e}")
            return 0

    def record_favorite_query(self, user_id: int, actress_name: str) -> bool:
        try:
            if self._is_query_rate_limited(user_id, actress_name):
                logger.debug(f"用户 {user_id} 查询 {actress_name} 超过频率限制，跳过记录")
                return False
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    'INSERT INTO favorite_queries (user_id, actress_name) VALUES (?, ?)',
                    (user_id, actress_name)
                )
                self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"记录查询历史失败: {e}")
            return False

    def get_recent_favorite_queries(self, user_id: int, limit: int = 10) -> List[Dict]:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    '''
                    SELECT actress_name, query_time
                    FROM favorite_queries
                    WHERE user_id = ?
                    ORDER BY query_time DESC
                    LIMIT ?
                    ''',
                    (user_id, limit)
                )
                rows = cursor.fetchall()
                return [{'actress_name': row[0], 'query_time': row[1]} for row in rows]
        except Exception as e:
            logger.error(f"获取查询记录失败: {e}")
            return []

    def get_most_frequent_favorites(self, user_id: int, limit: int = 5) -> List[Tuple[str, int]]:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    '''
                    SELECT actress_name, COUNT(*) as query_count
                    FROM favorite_queries
                    WHERE user_id = ?
                    GROUP BY actress_name
                    ORDER BY query_count DESC
                    LIMIT ?
                    ''',
                    (user_id, limit)
                )
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"获取最常查询收藏失败: {e}")
            return []

    def record_actress_work(self, actress_name: str, av_id: str, title: str = None, date: str = None, url: str = None, img: str = None) -> bool:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    '''
                    INSERT OR IGNORE INTO actress_works
                    (actress_name, av_id, title, date, url, img)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (actress_name, av_id, title, date, url, img)
                )
                self._conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"记录女优作品失败: {e}")
            return False

    def is_work_recorded(self, actress_name: str, av_id: str) -> bool:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM actress_works WHERE actress_name = ? AND av_id = ?',
                    (actress_name, av_id)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查作品记录失败: {e}")
            return False

    def get_actress_works(self, actress_name: str, limit: int = 50) -> List[Dict]:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    '''
                    SELECT av_id, title, date, url, img, created_at
                    FROM actress_works
                    WHERE actress_name = ?
                    ORDER BY date DESC
                    LIMIT ?
                    ''',
                    (actress_name, limit)
                )
                columns = ['av_id', 'title', 'date', 'url', 'img', 'created_at']
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取女优作品失败: {e}")
            return []

    def get_push_settings(self, user_id: int) -> dict:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute('SELECT * FROM user_push_settings WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return {'push_enabled': 1, 'last_check': None}
        except Exception as e:
            logger.error(f"获取推送设置失败: {e}")
            return {'push_enabled': 1, 'last_check': None}

    def set_push_enabled(self, user_id: int, enabled: bool) -> bool:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO user_push_settings (user_id, push_enabled, last_check)
                    VALUES (?, ?, COALESCE((SELECT last_check FROM user_push_settings WHERE user_id = ?), CURRENT_TIMESTAMP))
                    ''',
                    (user_id, 1 if enabled else 0, user_id)
                )
                self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"设置推送开关失败: {e}")
            return False

    def update_last_check(self, user_id: int) -> bool:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO user_push_settings (user_id, push_enabled, last_check)
                    VALUES (?, COALESCE((SELECT push_enabled FROM user_push_settings WHERE user_id = ?), 1), CURRENT_TIMESTAMP)
                    ''',
                    (user_id, user_id)
                )
                self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新检查时间失败: {e}")
            return False

    def get_users_with_push_enabled(self) -> List[int]:
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute('SELECT user_id FROM user_push_settings WHERE push_enabled = 1')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取推送用户列表失败: {e}")
            return []

    def cleanup_old_data(self, days: int = 90):
        try:
            cutoff_queries = (datetime.now() - timedelta(days=days)).isoformat()
            cutoff_works = (datetime.now() - timedelta(days=days * 2)).isoformat()
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    'DELETE FROM favorite_queries WHERE query_time < ?',
                    (cutoff_queries,)
                )
                deleted_queries = cursor.rowcount
                cursor.execute(
                    'DELETE FROM actress_works WHERE created_at < ?',
                    (cutoff_works,)
                )
                deleted_works = cursor.rowcount
                self._conn.commit()
            if deleted_queries > 0 or deleted_works > 0:
                logger.info(f"清理过期数据: 删除 {deleted_queries} 条查询记录, {deleted_works} 条作品记录")
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")

    def optimize_database(self):
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute("VACUUM")
                cursor.execute("ANALYZE")
            logger.info("数据库优化完成")
        except Exception as e:
            logger.error(f"数据库优化失败: {e}")


_favorites_manager = None


def get_favorites_manager() -> FavoritesManager:
    global _favorites_manager
    if _favorites_manager is None:
        _favorites_manager = FavoritesManager()
    return _favorites_manager
