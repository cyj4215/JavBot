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
            # 优先从环境变量获取数据库路径
            db_path = os.getenv("FAVORITES_DB_PATH")
            if not db_path:
                # 默认存储在用户目录下
                home_dir = Path.home()
                db_path = str(home_dir / ".openclaw" / "javbot_favorites.db")
        
        self.db_path = db_path
        logger.info(f"初始化收藏管理器，数据库路径: {self.db_path}")
        self._init_db()
        logger.info(f"收藏管理器初始化完成")
    
    def _init_db(self):
        """初始化数据库表"""
        logger.debug(f"开始初始化数据库，路径: {self.db_path}")
        
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
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
                actress_data TEXT,  -- JSON格式的完整女优信息
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actress_works_name ON actress_works(actress_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actress_works_name_id ON actress_works(actress_name, av_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actress_works_date ON actress_works(date DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_push_last_check ON user_push_settings(last_check)')
        
        conn.commit()
        logger.info("数据库初始化完成")
    
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
            # 确保用户存在
            self._ensure_user(user_id)
            
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
    
    def record_actress_work(self, actress_name: str, av_id: str, title: str = None, date: str = None, url: str = None, img: str = None) -> bool:
        """记录女优作品，返回是否是新作品
        
        Args:
            actress_name: 女优名称
            av_id: 作品番号
            title: 作品标题
            date: 发布日期
            url: 作品链接
            img: 封面链接
            
        Returns:
            bool: True 表示是新作品，False 表示已存在
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT OR IGNORE INTO actress_works 
                    (actress_name, av_id, title, date, url, img) 
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (actress_name, av_id, title, date, url, img)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"记录女优作品失败: {e}")
            return False
    
    def is_work_recorded(self, actress_name: str, av_id: str) -> bool:
        """检查作品是否已记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT 1 FROM actress_works WHERE actress_name = ? AND av_id = ?',
                    (actress_name, av_id)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查作品记录失败: {e}")
            return False
    
    def get_actress_works(self, actress_name: str, limit: int = 50) -> List[Dict]:
        """获取女优已记录的作品列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
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
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取女优作品失败: {e}")
            return []
    
    def get_push_settings(self, user_id: int) -> dict:
        """获取用户推送设置"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM user_push_settings WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return {'push_enabled': True, 'last_check': None}
        except Exception as e:
            logger.error(f"获取推送设置失败: {e}")
            return {'push_enabled': True, 'last_check': None}
    
    def set_push_enabled(self, user_id: int, enabled: bool) -> bool:
        """设置用户推送开关"""
        try:
            self._ensure_user(user_id)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO user_push_settings (user_id, push_enabled, last_check)
                    VALUES (?, ?, COALESCE((SELECT last_check FROM user_push_settings WHERE user_id = ?), CURRENT_TIMESTAMP))
                    ''',
                    (user_id, 1 if enabled else 0, user_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"设置推送开关失败: {e}")
            return False
    
    def update_last_check(self, user_id: int) -> bool:
        """更新用户最后检查时间"""
        try:
            self._ensure_user(user_id)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO user_push_settings (user_id, push_enabled, last_check)
                    VALUES (?, COALESCE((SELECT push_enabled FROM user_push_settings WHERE user_id = ?), 1), CURRENT_TIMESTAMP)
                    ''',
                    (user_id, user_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"更新检查时间失败: {e}")
            return False
    
    def get_users_with_push_enabled(self) -> List[int]:
        """获取所有开启推送的用户ID列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM user_push_settings WHERE push_enabled = 1')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取推送用户列表失败: {e}")
            return []


# 全局实例
_favorites_manager = None


def get_favorites_manager() -> FavoritesManager:
    """获取收藏管理器单例"""
    global _favorites_manager
    if _favorites_manager is None:
        _favorites_manager = FavoritesManager()
    return _favorites_manager