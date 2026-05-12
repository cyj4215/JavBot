import json
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    """Thread-safe TTL cache with optional JSON persistence."""

    def __init__(self, max_size: int = 1024, default_ttl: int = 600, persist_path: Optional[str] = None):
        self.max_size = max(64, max_size)
        self.default_ttl = max(30, default_ttl)
        self._persist_path = persist_path
        self._lock = threading.RLock()
        self._data: OrderedDict = OrderedDict()
        self._dirty = False
        self._last_save = 0.0
        self._save_debounce = 5.0
        self._load()

    def _load(self) -> None:
        if not self._persist_path:
            return
        try:
            if os.path.exists(self._persist_path):
                with open(self._persist_path) as f:
                    raw = json.load(f)
                now = time.time()
                for key_json, (expire_at, value) in raw.items():
                    if expire_at > now:
                        try:
                            key = json.loads(key_json)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        self._data[key] = (expire_at, value)
                while len(self._data) > self.max_size:
                    self._data.popitem(last=False)
        except Exception:
            pass

    def _save(self) -> None:
        if not self._persist_path:
            return
        now = time.time()
        if now - self._last_save < self._save_debounce:
            return
        try:
            serializable: OrderedDict = OrderedDict()
            for key, (expire_at, value) in self._data.items():
                if expire_at < now:
                    continue
                try:
                    key_json = json.dumps(key, ensure_ascii=False)
                    json.dumps(value)  # validate serializable
                    serializable[key_json] = (expire_at, value)
                except (TypeError, ValueError):
                    continue
            tmp = self._persist_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(serializable, f, ensure_ascii=False)
            os.replace(tmp, self._persist_path)
            self._last_save = time.time()
        except Exception:
            pass

    def get(self, key) -> Any:
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expire_at, value = item
            if expire_at < now:
                self._data.pop(key, None)
                self._dirty = True
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key, value, ttl: Optional[int] = None):
        expire_at = time.time() + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            if key in self._data:
                self._data.pop(key, None)
            self._data[key] = (expire_at, value)
            while len(self._data) > self.max_size:
                self._data.popitem(last=False)
            self._dirty = True
        self._save()

    def delete(self, key) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._dirty = True
        self._save()

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._dirty = True
        self._save()

    def cleanup(self) -> int:
        """Remove expired entries. Returns count removed."""
        now = time.time()
        removed = 0
        with self._lock:
            to_delete = [k for k, (expire_at, _) in self._data.items() if expire_at < now]
            for k in to_delete:
                self._data.pop(k, None)
                removed += 1
            if removed:
                self._dirty = True
        return removed

    @property
    def dirty(self) -> bool:
        return self._dirty

    def save(self) -> None:
        """Force save to disk."""
        self._save()

    def __contains__(self, key) -> bool:
        return self.get(key) is not None

    def __getitem__(self, key) -> Any:
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key, value) -> None:
        self.set(key, value)

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
