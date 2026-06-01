"""
收藏功能模块 — 异步 MySQL 实现 (aiomysql)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiomysql

logger = logging.getLogger(__name__)

QUERY_FREQUENCY_LIMIT = 10
QUERY_FREQUENCY_WINDOW = 3600

_SQL_INIT = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username VARCHAR(255),
        first_name VARCHAR(255),
        last_name VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS favorites (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        actress_name VARCHAR(255) NOT NULL,
        actress_id VARCHAR(255),
        actress_data JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        UNIQUE KEY uk_user_actress (user_id, actress_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS favorite_queries (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        actress_name VARCHAR(255) NOT NULL,
        query_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        INDEX idx_fq_user (user_id),
        INDEX idx_fq_time (query_time),
        INDEX idx_fq_user_actress_time (user_id, actress_name, query_time)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actress_works (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        actress_name VARCHAR(255) NOT NULL,
        av_id VARCHAR(255) NOT NULL,
        title VARCHAR(500),
        date VARCHAR(20),
        url VARCHAR(500),
        img TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_actress_av (actress_name, av_id),
        INDEX idx_aw_date (date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_push_settings (
        user_id BIGINT PRIMARY KEY,
        push_enabled BOOLEAN DEFAULT 1,
        last_check TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        INDEX idx_ups_last_check (last_check),
        INDEX idx_ups_push_enabled (push_enabled)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id BIGINT PRIMARY KEY,
        language VARCHAR(10) DEFAULT 'zh_CN',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tracking_stats (
        stat_key VARCHAR(100) PRIMARY KEY,
        stat_value BIGINT DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
    """,
]


class FavoritesManager:

    def __init__(self, pool: aiomysql.Pool):
        self._pool = pool

    @classmethod
    async def create(cls, config) -> "FavoritesManager":
        """Create manager with connection pool and initialize tables."""
        pool = await aiomysql.create_pool(
            host=config.mysql_host,
            port=config.mysql_port,
            user=config.mysql_user,
            password=config.mysql_password,
            db=config.mysql_database,
            minsize=1,
            maxsize=5,
            autocommit=False,
            cursorclass=aiomysql.cursors.DictCursor,
        )
        manager = cls(pool)
        await manager._init_tables()
        logger.info("MySQL 连接池已创建，表结构已初始化")
        return manager

    async def close(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info("MySQL 连接池已关闭")

    async def _init_tables(self) -> None:
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                for ddl in _SQL_INIT:
                    await cur.execute(ddl)
                await conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _select_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchone()

    async def _select_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchall()

    async def _execute(self, query: str, params: tuple = ()) -> int:
        """Execute a single write query with commit. Returns rowcount."""
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                await conn.commit()
                return cur.rowcount

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    async def sync_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> bool:
        try:
            await self._execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    username = COALESCE(VALUES(username), username),
                    first_name = COALESCE(VALUES(first_name), first_name),
                    last_name = COALESCE(VALUES(last_name), last_name)
                """,
                (user_id, username, first_name, last_name),
            )
            return True
        except Exception as e:
            logger.error(f"同步用户信息失败: {e}")
            return False

    # ------------------------------------------------------------------
    # Favorites CRUD
    # ------------------------------------------------------------------

    async def add_favorite(
        self,
        user_id: int,
        actress_name: str,
        actress_id: Optional[str] = None,
        actress_data: Optional[dict] = None,
    ) -> bool:
        try:
            await self.sync_user(user_id)
            extra_only = {"extra_info": actress_data.get("extra_info")} if actress_data and actress_data.get("extra_info") else None
            actress_data_json = json.dumps(extra_only, ensure_ascii=False) if extra_only else None

            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    existing = await cur.execute(
                        "SELECT id FROM favorites WHERE user_id = %s AND actress_name = %s",
                        (user_id, actress_name),
                    )
                    if existing:
                        await cur.execute(
                            """
                            UPDATE favorites
                            SET actress_id = COALESCE(%s, actress_id),
                                actress_data = COALESCE(%s, actress_data)
                            WHERE user_id = %s AND actress_name = %s
                            """,
                            (actress_id, actress_data_json, user_id, actress_name),
                        )
                    else:
                        await cur.execute(
                            """
                            INSERT INTO favorites (user_id, actress_name, actress_id, actress_data)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (user_id, actress_name, actress_id, actress_data_json),
                        )
                    await conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加收藏失败: {e}")
            return False

    async def remove_favorite(self, user_id: int, actress_name: str) -> bool:
        try:
            affected = await self._execute(
                "DELETE FROM favorites WHERE user_id = %s AND actress_name = %s",
                (user_id, actress_name),
            )
            return affected > 0
        except Exception as e:
            logger.error(f"移除收藏失败: {e}")
            return False

    async def get_favorites(
        self,
        user_id: int,
        limit: int = 10,
        cursor: Optional[Tuple[str, int]] = None,
    ) -> Dict[str, Any]:
        try:
            if cursor is not None:
                created_at_val, row_id_val = cursor
                where = "WHERE user_id = %s AND (created_at < %s OR (created_at = %s AND id < %s))"
                params: tuple = (user_id, created_at_val, created_at_val, row_id_val)
            else:
                where = "WHERE user_id = %s"
                params = (user_id,)

            count_row = await self._select_one(f"SELECT COUNT(*) AS cnt FROM favorites {where}", params)
            total = count_row["cnt"] if count_row else 0

            rows = await self._select_all(
                f"""
                SELECT id, actress_name, actress_id, actress_data, created_at
                FROM favorites
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (*params, limit),
            )

            favorites = []
            for row in rows:
                fav = {
                    "id": row["id"],
                    "actress_name": row["actress_name"],
                    "actress_id": row["actress_id"],
                    "created_at": str(row["created_at"]) if row.get("created_at") else None,
                }
                if row.get("actress_data"):
                    try:
                        fav["actress_data"] = json.loads(row["actress_data"])
                    except Exception:
                        logger.debug("解析收藏数据 JSON 失败", exc_info=True)
                        fav["actress_data"] = None
                favorites.append(fav)

            next_cursor: Optional[Tuple[str, int]] = None
            if len(favorites) == limit and favorites:
                last = favorites[-1]
                next_cursor = (last["created_at"], last["id"])

            return {"items": favorites, "next_cursor": next_cursor, "total": total}
        except Exception as e:
            logger.error(f"获取收藏列表失败: {e}")
            return {"items": [], "next_cursor": None, "total": 0}

    async def is_favorite(self, user_id: int, actress_name: str) -> bool:
        try:
            row = await self._select_one(
                "SELECT 1 AS val FROM favorites WHERE user_id = %s AND actress_name = %s",
                (user_id, actress_name),
            )
            return row is not None
        except Exception as e:
            logger.error(f"检查收藏状态失败: {e}")
            return False

    async def get_favorite_count(self, user_id: int) -> int:
        try:
            row = await self._select_one(
                "SELECT COUNT(*) AS cnt FROM favorites WHERE user_id = %s",
                (user_id,),
            )
            return row["cnt"] if row else 0
        except Exception as e:
            logger.error(f"获取收藏数量失败: {e}")
            return 0

    # ------------------------------------------------------------------
    # Favorite queries tracking
    # ------------------------------------------------------------------

    async def _is_query_rate_limited(self, user_id: int, actress_name: str) -> bool:
        window_start = (datetime.now() - timedelta(seconds=QUERY_FREQUENCY_WINDOW)).isoformat()
        row = await self._select_one(
            """
            SELECT COUNT(*) AS cnt FROM favorite_queries
            WHERE user_id = %s AND actress_name = %s AND query_time > %s
            """,
            (user_id, actress_name, window_start),
        )
        count = row["cnt"] if row else 0
        return count >= QUERY_FREQUENCY_LIMIT

    async def record_favorite_query(self, user_id: int, actress_name: str) -> bool:
        try:
            if await self._is_query_rate_limited(user_id, actress_name):
                logger.debug(f"用户 {user_id} 查询 {actress_name} 超过频率限制，跳过记录")
                return False
            await self._execute(
                "INSERT INTO favorite_queries (user_id, actress_name) VALUES (%s, %s)",
                (user_id, actress_name),
            )
            return True
        except Exception as e:
            logger.error(f"记录查询历史失败: {e}")
            return False

    async def get_recent_favorite_queries(self, user_id: int, limit: int = 10) -> List[Dict]:
        try:
            rows = await self._select_all(
                """
                SELECT actress_name, query_time
                FROM favorite_queries
                WHERE user_id = %s
                ORDER BY query_time DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [{"actress_name": r["actress_name"], "query_time": str(r["query_time"])} for r in rows]
        except Exception as e:
            logger.error(f"获取查询记录失败: {e}")
            return []

    async def get_most_frequent_favorites(self, user_id: int, limit: int = 5) -> List[Tuple[str, int]]:
        try:
            rows = await self._select_all(
                """
                SELECT actress_name, COUNT(*) AS query_count
                FROM favorite_queries
                WHERE user_id = %s
                GROUP BY actress_name
                ORDER BY query_count DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [(r["actress_name"], r["query_count"]) for r in rows]
        except Exception as e:
            logger.error(f"获取最常查询收藏失败: {e}")
            return []

    async def get_last_query_time_map(self, user_id: int) -> Dict[str, str]:
        """Get the most recent query time for each favorite actress."""
        try:
            rows = await self._select_all(
                """
                SELECT f.actress_name, MAX(fq.query_time) AS last_query
                FROM favorites f
                LEFT JOIN favorite_queries fq ON fq.user_id = f.user_id AND fq.actress_name = f.actress_name
                WHERE f.user_id = %s
                GROUP BY f.actress_name
                """,
                (user_id,),
            )
            result: Dict[str, str] = {}
            for r in rows:
                val = r.get("last_query")
                result[r["actress_name"]] = str(val)[:16] if val and val is not None else ""
            return result
        except Exception as e:
            logger.error(f"获取查询时间失败: {e}")
            return {}

    # ------------------------------------------------------------------
    # Actress works tracking
    # ------------------------------------------------------------------

    async def record_actress_work(
        self,
        actress_name: str,
        av_id: str,
        title: Optional[str] = None,
        date: Optional[str] = None,
        url: Optional[str] = None,
        img: Optional[str] = None,
    ) -> bool:
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT IGNORE INTO actress_works
                        (actress_name, av_id, title, date, url, img)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (actress_name, av_id, title, date, url, img),
                    )
                    await conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"记录女优作品失败: {e}")
            return False

    async def is_work_recorded(self, actress_name: str, av_id: str) -> bool:
        try:
            row = await self._select_one(
                "SELECT 1 AS val FROM actress_works WHERE actress_name = %s AND av_id = %s",
                (actress_name, av_id),
            )
            return row is not None
        except Exception as e:
            logger.error(f"检查作品记录失败: {e}")
            return False

    async def get_actress_works(self, actress_name: str, limit: int = 50) -> List[Dict]:
        try:
            rows = await self._select_all(
                """
                SELECT av_id, title, date, url, img, created_at
                FROM actress_works
                WHERE actress_name = %s
                ORDER BY date DESC
                LIMIT %s
                """,
                (actress_name, limit),
            )
            columns = ["av_id", "title", "date", "url", "img", "created_at"]
            return [{c: r[c] for c in columns} for r in rows]
        except Exception as e:
            logger.error(f"获取女优作品失败: {e}")
            return []

    # ------------------------------------------------------------------
    # Push settings
    # ------------------------------------------------------------------

    async def batch_remove(self, user_id: int, names: List[str]) -> int:
        """Remove multiple favorites at once. Returns count removed."""
        if not names:
            return 0
        try:
            placeholders = ", ".join(["%s"] * len(names))
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"DELETE FROM favorites WHERE user_id = %s AND actress_name IN ({placeholders})",
                        (user_id, *names),
                    )
                    removed = cur.rowcount
                    await conn.commit()
                    return removed
        except Exception as e:
            logger.error(f"批量移除收藏失败: {e}")
            return 0

    async def export_favorites(self, user_id: int) -> Optional[str]:
        """Export favorites as JSON string. Returns None if no favorites."""
        try:
            result = await self.get_favorites(user_id, limit=1000)
            items = result.get("items", [])
            if not items:
                return None
            return json.dumps(items, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"导出收藏失败: {e}")
            return None

    async def get_push_settings(self, user_id: int) -> dict:
        try:
            row = await self._select_one(
                "SELECT * FROM user_push_settings WHERE user_id = %s",
                (user_id,),
            )
            if row:
                return {
                    "push_enabled": row["push_enabled"],
                    "last_check": str(row["last_check"]) if row.get("last_check") else None,
                }
            return {"push_enabled": 1, "last_check": None}
        except Exception as e:
            logger.error(f"获取推送设置失败: {e}")
            return {"push_enabled": 1, "last_check": None}

    async def set_push_enabled(self, user_id: int, enabled: bool) -> bool:
        try:
            await self._execute(
                """
                INSERT INTO user_push_settings (user_id, push_enabled, last_check)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    push_enabled = VALUES(push_enabled)
                """,
                (user_id, 1 if enabled else 0),
            )
            return True
        except Exception as e:
            logger.error(f"设置推送开关失败: {e}")
            return False

    async def update_last_check(self, user_id: int) -> bool:
        try:
            await self._execute(
                """
                INSERT INTO user_push_settings (user_id, push_enabled, last_check)
                VALUES (%s, 1, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    last_check = CURRENT_TIMESTAMP
                """,
                (user_id,),
            )
            return True
        except Exception as e:
            logger.error(f"更新检查时间失败: {e}")
            return False

    async def get_users_with_push_enabled(self) -> List[int]:
        try:
            rows = await self._select_all(
                """
                SELECT DISTINCT f.user_id
                FROM favorites f
                LEFT JOIN user_push_settings ups ON f.user_id = ups.user_id
                WHERE ups.user_id IS NULL OR ups.push_enabled = 1
                """,
            )
            return [r["user_id"] for r in rows]
        except Exception as e:
            logger.error(f"获取推送用户列表失败: {e}")
            return []

    # ------------------------------------------------------------------
    # Cleanup & maintenance
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Usage statistics
    # ------------------------------------------------------------------

    async def increment_stat(self, stat_key: str, amount: int = 1) -> bool:
        """Atomically increment a global usage stat."""
        try:
            await self._execute(
                """
                INSERT INTO tracking_stats (stat_key, stat_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE stat_value = stat_value + VALUES(stat_value)
                """,
                (stat_key, amount),
            )
            return True
        except Exception as e:
            logger.error(f"更新统计失败: {e}")
            return False

    async def get_all_stats(self) -> dict:
        """Return all tracking stats as dict."""
        try:
            rows = await self._select_all("SELECT stat_key, stat_value FROM tracking_stats")
            return {r["stat_key"]: r["stat_value"] for r in rows}
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {}

    # ------------------------------------------------------------------
    # User settings
    # ------------------------------------------------------------------

    async def get_user_language(self, user_id: int) -> str:
        try:
            row = await self._select_one(
                "SELECT language FROM user_settings WHERE user_id = %s",
                (user_id,),
            )
            return row["language"] if row else "zh_CN"
        except Exception as e:
            logger.error(f"获取用户语言设置失败: {e}")
            return "zh_CN"

    async def set_user_language(self, user_id: int, language: str) -> bool:
        try:
            await self.sync_user(user_id)
            await self._execute(
                """
                INSERT INTO user_settings (user_id, language)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE language = VALUES(language)
                """,
                (user_id, language),
            )
            return True
        except Exception as e:
            logger.error(f"设置用户语言失败: {e}")
            return False

    async def cleanup_old_data(self, days: int = 90) -> None:
        try:
            cutoff_queries = (datetime.now() - timedelta(days=days)).isoformat()
            cutoff_works = (datetime.now() - timedelta(days=days * 2)).isoformat()
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM favorite_queries WHERE query_time < %s",
                        (cutoff_queries,),
                    )
                    deleted_queries = cur.rowcount
                    await cur.execute(
                        "DELETE FROM actress_works WHERE created_at < %s",
                        (cutoff_works,),
                    )
                    deleted_works = cur.rowcount
                    await conn.commit()
            if deleted_queries > 0 or deleted_works > 0:
                logger.info(f"清理过期数据: 删除 {deleted_queries} 条查询记录, {deleted_works} 条作品记录")
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")

    async def optimize_database(self) -> None:
        """MySQL analog: OPTIMIZE TABLE to reclaim space."""
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for tbl in ("favorite_queries", "actress_works", "favorites", "user_push_settings"):
                        await cur.execute(f"OPTIMIZE TABLE {tbl}")
                    await conn.commit()
            logger.info("数据库优化完成")
        except Exception as e:
            logger.error(f"数据库优化失败: {e}")


_favorites_manager: Optional[FavoritesManager] = None


async def get_favorites_manager(config=None) -> FavoritesManager:
    global _favorites_manager
    if _favorites_manager is None:
        if config is None:
            raise RuntimeError("FavoritesManager not initialized. Pass config on first call.")
        _favorites_manager = await FavoritesManager.create(config)
    return _favorites_manager


async def close_favorites_manager() -> None:
    global _favorites_manager
    if _favorites_manager is not None:
        await _favorites_manager.close()
        _favorites_manager = None
