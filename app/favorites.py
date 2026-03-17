"""
收藏功能模块 - 用于存储和管理用户收藏的女优
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class FavoritesManager:
    """收藏管理器"""
    
    def __init__(self, db_path: str = None):
        """初始化收藏管理器
        
        Args:
            db_path: SQLite数据库路径，默认为 ~/.openclaw/javbot_favorites.db
        """
        if db_path is None:
            # 默认存储在用户目录下
            home_dir = Path.home()
            db_path = str(home_dir / ".openclaw" / "javbot_favorites.db")
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if db_dir:  # 确保目录存在
                os.makedirs(db_dir, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建收藏表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                actress_name TEXT NOT NULL,
                actress_id TEXT,
                actress_data TEXT,  -- JSON格式的完整女优信息
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, actress_name)
            )
        ''')
        
        # 创建收藏查询历史表（用于记录用户点击收藏查询最新作品）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorite_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                actress_name TEXT NOT NULL,
                query_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user_name ON favorites(user_id, actress_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorite_queries_user ON favorite_queries(user_id)')
        
        conn.commit()
    
    def _ensure_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """确保用户存在"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
                (user_id, username, first_name, last_name)
            )
            conn.commit()
    
    def add_favorite(self, user_id: int, actress_name: str, actress_id: str = None, actress_data: dict = None) -> bool:
        """添加收藏
        
        Args:
            user_id: 用户ID
            actress_name: 女优名称
            actress_id: 女优ID（可选）
            actress_data: 完整的女优信息（可选，JSON格式）
            
        Returns:
            bool: 是否添加成功
        """
        try:
            actress_data_json = json.dumps(actress_data, ensure_ascii=False) if actress_data else None
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO favorites 
                    (user_id, actress_name, actress_id, actress_data) 
                    VALUES (?, ?, ?, ?)
                    ''',
                    (user_id, actress_name, actress_id, actress_data_json)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加收藏失败: {e}")
            return False
    
    def remove_favorite(self, user_id: int, actress_name: str) -> bool:
        """移除收藏
        
        Args:
            user_id: 用户ID
            actress_name: 女优名称
            
        Returns:
            bool: 是否移除成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM favorites WHERE user_id = ? AND actress_name = ?',
                    (user_id, actress_name)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"移除收藏失败: {e}")
            return False
    
    def get_favorites(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取用户的收藏列表
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            List[Dict]: 收藏列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT actress_name, actress_id, actress_data, created_at
                    FROM favorites 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    ''',
                    (user_id, limit, offset)
                )
                rows = cursor.fetchall()
                
                favorites = []
                for row in rows:
                    favorite = {
                        'actress_name': row['actress_name'],
                        'actress_id': row['actress_id'],
                        'created_at': row['created_at']
                    }
                    if row['actress_data']:
                        try:
                            favorite['actress_data'] = json.loads(row['actress_data'])
                        except:
                            favorite['actress_data'] = None
                    favorites.append(favorite)
                
                return favorites
        except Exception as e:
            logger.error(f"获取收藏列表失败: {e}")
            return []
    
    def is_favorite(self, user_id: int, actress_name: str) -> bool:
        """检查是否已收藏
        
        Args:
            user_id: 用户ID
            actress_name: 女优名称
            
        Returns:
            bool: 是否已收藏
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM favorites WHERE user_id = ? AND actress_name = ?',
                    (user_id, actress_name)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查收藏状态失败: {e}")
            return False
    
    def get_favorite_count(self, user_id: int) -> int:
        """获取用户收藏数量
        
        Args:
            user_id: 用户ID
            
        Returns:
            int: 收藏数量
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT COUNT(*) FROM favorites WHERE user_id = ?',
                    (user_id,)
                )
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"获取收藏数量失败: {e}")
            return 0
    
    def record_favorite_query(self, user_id: int, actress_name: str):
        """记录收藏查询历史（用于统计）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO favorite_queries (user_id, actress_name) VALUES (?, ?)',
                    (user_id, actress_name)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"记录查询历史失败: {e}")
    
    def get_recent_favorite_queries(self, user_id: int, limit: int = 10) -> List[Dict]:
        """获取最近的收藏查询记录
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 查询记录列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
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
                
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取查询记录失败: {e}")
            return []
    
    def get_most_frequent_favorites(self, user_id: int, limit: int = 5) -> List[Tuple[str, int]]:
        """获取最常查询的收藏（按查询次数排序）
        
        Args:
            user_id: 用户ID
            limit: 返回数量限制
            
        Returns:
            List[Tuple[str, int]]: (女优名称, 查询次数) 列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
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


# 全局实例
_favorites_manager = None


def get_favorites_manager() -> FavoritesManager:
    """获取收藏管理器单例"""
    global _favorites_manager
    if _favorites_manager is None:
        _favorites_manager = FavoritesManager()
    return _favorites_manager