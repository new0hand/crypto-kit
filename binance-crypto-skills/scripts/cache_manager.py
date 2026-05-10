# -*- coding: utf-8 -*-
"""
数据缓存管理器（加密货币版）

功能:
- SQLite 本地缓存
- 自动过期管理
- 支持多种数据类型

用法:
    from cache_manager import CacheManager
    cache = CacheManager()
    cache.set('key', data, expire_seconds=3600)
    data = cache.get('key')
"""
import sqlite3
import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional

# 默认缓存目录
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.cache')
DB_PATH = os.path.join(CACHE_DIR, 'binance_cache.db')

# 缓存过期时间配置（秒）
# 加密货币 7x24 交易，缓存时间比 A 股短
CACHE_EXPIRE = {
    'realtime': 30,             # 实时行情: 30秒
    'kline_1m': 60,             # 1分钟K线: 1分钟
    'kline_5m': 300,            # 5分钟K线: 5分钟
    'kline_1h': 1800,           # 1小时K线: 30分钟
    'kline_1d': 3600,           # 日K线: 1小时
    'futures_kline': 1800,      # 期货K线: 30分钟
    'ticker_24h': 60,           # 24h行情: 1分钟
    'orderbook': 10,            # 盘口: 10秒
    'trades': 30,               # 最近成交: 30秒
    'funding_rate': 300,        # 资金费率: 5分钟
    'open_interest': 300,       # 持仓量: 5分钟
}


class CacheManager:
    """数据缓存管理器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._ensure_cache_dir()
        self._init_db()

    def _ensure_cache_dir(self):
        cache_dir = os.path.dirname(self.db_path)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    expire_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def _generate_key(self, category: str, *args, **kwargs) -> str:
        key_parts = [category] + list(args)
        if kwargs:
            key_parts.append(json.dumps(kwargs, sort_keys=True))
        raw_key = ':'.join(str(p) for p in key_parts)
        return hashlib.md5(raw_key.encode()).hexdigest()

    def set(self, key: str, value: Any, expire_seconds: int = 3600) -> bool:
        try:
            expire_at = datetime.now() + timedelta(seconds=expire_seconds)
            value_json = json.dumps(value, default=str, ensure_ascii=False)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO cache (key, value, expire_at)
                    VALUES (?, ?, ?)
                ''', (key, value_json, expire_at))
                conn.commit()
            return True
        except Exception as e:
            print(f"缓存写入失败: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT value, expire_at FROM cache WHERE key = ?', (key,))
                row = cursor.fetchone()
                if row is None:
                    return None
                value_json, expire_at = row
                expire_time = datetime.fromisoformat(expire_at)
                if datetime.now() > expire_time:
                    self.delete(key)
                    return None
                return json.loads(value_json)
        except Exception as e:
            print(f"缓存读取失败: {e}")
            return None

    def delete(self, key: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM cache WHERE key = ?', (key,))
                conn.commit()
            return True
        except Exception:
            return False

    def clear_expired(self) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'DELETE FROM cache WHERE expire_at < ?', (datetime.now(),))
                conn.commit()
                return cursor.rowcount
        except Exception:
            return 0

    def clear_all(self) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM cache')
                conn.commit()
            return True
        except Exception:
            return False

    def get_stats(self) -> dict:
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute('SELECT COUNT(*) FROM cache').fetchone()[0]
                expired = conn.execute(
                    'SELECT COUNT(*) FROM cache WHERE expire_at < ?',
                    (datetime.now(),)).fetchone()[0]
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                return {
                    'total': total,
                    'expired': expired,
                    'valid': total - expired,
                    'db_size_mb': round(db_size / 1024 / 1024, 2)
                }
        except Exception:
            return {}


# 全局缓存实例
_cache = None

def get_cache() -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache

def cache_get(category: str, *args, **kwargs):
    cache = get_cache()
    key = cache._generate_key(category, *args, **kwargs)
    return cache.get(key)

def cache_set(category: str, value: Any, *args, expire_seconds: int = None, **kwargs):
    cache = get_cache()
    key = cache._generate_key(category, *args, **kwargs)
    if expire_seconds is None:
        expire_seconds = CACHE_EXPIRE.get(category, 3600)
    return cache.set(key, value, expire_seconds)


if __name__ == '__main__':
    cache = CacheManager()
    print("币安缓存管理器测试")
    print("-" * 40)
    cache.set('test_key', {'symbol': 'BTCUSDT', 'price': 100000}, expire_seconds=60)
    print("设置缓存: test_key")
    data = cache.get('test_key')
    print(f"读取缓存: {data}")
    stats = cache.get_stats()
    print(f"缓存统计: {stats}")
