from __future__ import annotations

import asyncio
import threading
import time


class RateLimiter:
    def __init__(self, calls_per_second: float = 1.0):
        self._min_interval = 1.0 / calls_per_second
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        """Blocking wait (for sync contexts / to_thread)."""
        with self._sync_lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.time()

    async def async_wait(self) -> None:
        """Non-blocking wait (for async contexts)."""
        async with self._async_lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_call = time.time()
