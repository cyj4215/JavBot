"""Secure callback storage with HMAC-SHA256 signatures and TTL support.

This module provides a secure way to store callback data with:
- HMAC-SHA256 signatures instead of MD5 for data integrity
- Time-based expiration (TTL) for stored data
- Automatic cleanup of expired entries
- JSON file persistence for container restarts
- Dirty flag + delayed save to reduce disk I/O
- Backward compatibility with old MD5 format (returns empty for security)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_CALLBACK_DB_PATH = os.environ.get("CALLBACK_DB_PATH", "/app/data/callbacks.json")


class SecureCallbackStore:
    """Thread-safe secure callback data store with HMAC-SHA256 signatures, TTL and JSON persistence.

    Format: prefix:key:signature:timestamp
    - prefix: callback type prefix (e.g., 'search', 'favquery')
    - key: random 8-character hex key
    - signature: HMAC-SHA256 signature (hex, 16 chars)
    - timestamp: Unix timestamp when created

    The signature is computed over: prefix + ':' + key + ':' + data
    """

    DEFAULT_TTL = 604800
    CLEANUP_INTERVAL = 60
    SIGNATURE_LENGTH = 16
    KEY_LENGTH = 8
    SAVE_INTERVAL = 30

    def __init__(self, ttl: int = DEFAULT_TTL, storage_path: str = DEFAULT_CALLBACK_DB_PATH) -> None:
        self._ttl = ttl
        self._storage_path = storage_path
        self._secret: bytes = secrets.token_bytes(32)
        self._store: Dict[Tuple[str, str], Tuple[str, float]] = {}
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._dirty = False
        self._last_save = 0.0
        self._load_from_file()

    def _generate_key(self) -> str:
        return secrets.token_hex(self.KEY_LENGTH // 2)

    def _compute_signature(self, prefix: str, key: str, data: str) -> str:
        message = f"{prefix}:{key}:{data}".encode('utf-8')
        signature = hmac.new(self._secret, message, hashlib.sha256).hexdigest()
        return signature[:self.SIGNATURE_LENGTH]

    def _verify_signature(self, prefix: str, key: str, data: str, signature: str) -> bool:
        expected = self._compute_signature(prefix, key, data)
        return hmac.compare_digest(expected, signature)

    def _is_expired(self, timestamp: float) -> bool:
        return time.time() - timestamp > self._ttl

    def _load_from_file(self) -> None:
        if not os.path.exists(self._storage_path):
            logger.info(f"Callback storage file not found, starting fresh: {self._storage_path}")
            return

        try:
            with open(self._storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            callbacks = data.get('callbacks', {})
            for key_str, value in callbacks.items():
                prefix, key = key_str.split(':', 1)
                self._store[(prefix, key)] = (value['data'], value['timestamp'])

            logger.info(f"Loaded {len(self._store)} callbacks from {self._storage_path}")
        except Exception as e:
            logger.warning(f"Failed to load callback storage: {e}, starting fresh")

    def _save_to_file(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            data = {
                'callbacks': {
                    f"{prefix}:{key}": {'data': value[0], 'timestamp': value[1]}
                    for (prefix, key), value in self._store.items()
                }
            }
            with open(self._storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            self._dirty = False
            self._last_save = time.time()
        except Exception as e:
            logger.error(f"Failed to save callback storage: {e}")

    def _maybe_save(self) -> None:
        if self._dirty and time.time() - self._last_save >= self.SAVE_INTERVAL:
            self._save_to_file()

    def _cleanup_expired(self) -> None:
        now = time.time()
        if now - self._last_cleanup < self.CLEANUP_INTERVAL:
            return

        with self._lock:
            expired_keys = [
                key for key, (_, timestamp) in self._store.items()
                if self._is_expired(timestamp)
            ]
            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired callback entries")
                self._dirty = True

            self._last_cleanup = now

        self._maybe_save()

    def create(self, prefix: str, data: str) -> str:
        self._cleanup_expired()

        key = self._generate_key()
        signature = self._compute_signature(prefix, key, data)
        timestamp = int(time.time())

        with self._lock:
            self._store[(prefix, key)] = (data, time.time())
            self._dirty = True

        self._maybe_save()

        callback_token = f"{prefix}:{key}:{signature}:{timestamp}"
        logger.debug(f"Created callback token: {prefix}:... (data length: {len(data)})")
        return callback_token

    def resolve(self, prefix: str, token: str) -> Optional[str]:
        self._cleanup_expired()

        if self._is_legacy_format(token):
            logger.warning(f"Rejected legacy MD5 format callback: {prefix}:...")
            return None

        parts = token.split(':')
        if len(parts) != 4:
            logger.warning(f"Invalid callback token format: {prefix}:...")
            return None

        token_prefix, key, signature, timestamp_str = parts

        if token_prefix != prefix:
            logger.warning(f"Callback prefix mismatch: expected {prefix}, got {token_prefix}")
            return None

        try:
            timestamp = int(timestamp_str)
        except ValueError:
            logger.warning(f"Invalid timestamp in callback: {prefix}:...")
            return None

        if self._is_expired(timestamp):
            logger.debug(f"Callback expired: {prefix}:{key}")
            with self._lock:
                self._store.pop((prefix, key), None)
                self._dirty = True
            self._maybe_save()
            return None

        with self._lock:
            stored = self._store.pop((prefix, key), None)

        if stored is None:
            logger.warning(f"Callback not found or already used: {prefix}:{key}")
            return None

        data, _ = stored

        if not self._verify_signature(prefix, key, data, signature):
            logger.warning(f"Invalid signature for callback: {prefix}:{key}")
            return None

        self._dirty = True
        logger.debug(f"Resolved and consumed callback: {prefix}:{key}")
        return data

    def _is_legacy_format(self, token: str) -> bool:
        parts = token.split(':')
        if len(parts) != 2:
            return False

        key = parts[1]
        if len(key) != 8:
            return False

        if not re.match(r'^[0-9a-f]{8}$', key, re.IGNORECASE):
            return False

        return True

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._store)
            expired = sum(
                1 for _, (_, timestamp) in self._store.items()
                if self._is_expired(timestamp)
            )

        return {
            "total_entries": total,
            "expired_entries": expired,
            "valid_entries": total - expired,
            "ttl_seconds": self._ttl,
            "cleanup_interval_seconds": self.CLEANUP_INTERVAL,
            "storage_path": self._storage_path,
        }

    def clear(self) -> None:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._dirty = True
            logger.info(f"Cleared {count} callback entries")

        self._save_to_file()

    def flush(self) -> None:
        if self._dirty:
            self._save_to_file()


_callback_store: Optional[SecureCallbackStore] = None
_store_lock = threading.Lock()


def get_callback_store() -> SecureCallbackStore:
    global _callback_store
    if _callback_store is None:
        with _store_lock:
            if _callback_store is None:
                storage_path = os.environ.get("CALLBACK_DB_PATH", DEFAULT_CALLBACK_DB_PATH)
                _callback_store = SecureCallbackStore(storage_path=storage_path)
    return _callback_store


def short_callback(prefix: str, data: str) -> str:
    return get_callback_store().create(prefix, data)


def resolve_callback(prefix: str, token: str) -> Optional[str]:
    return get_callback_store().resolve(prefix, token)
