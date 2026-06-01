# Medium-Priority Fixes Implementation Plan

> **For agentic workers:** Inline execution — batch 3 small fixes with manual review.

**Goal:** Fix 3 medium-priority issues from code audit: rate limiter gap, incorrect log level, browser pool cleanup edge case.

**Architecture:** Each fix is a self-contained 1-3 line change in a single file. No cross-file coordination needed.

**Tech Stack:** Python, threading, asyncio, atexit

---

### Task 1: Add rate limiter to `get_av_magnets`

**Files:**
- Modify: `app/services/javbus_service.py:92-112`

`get_av_magnets` calls `self.javbus.get_av_magnets()` without waiting for `self._javbus_limiter`, unlike `get_av_meta` which calls `self._javbus_limiter.wait()` at line 52. This can hit JavBus API rate limits under concurrent queries.

- [ ] **Add `self._javbus_limiter.wait()` before the `self.javbus.get_av_magnets()` call**

Change in `get_av_magnets` (line 95-96):
```python
        try:
            self._javbus_limiter.wait()
            code, magnets = self.javbus.get_av_magnets(av_id, is_uncensored=self.uncensored)
```

- [ ] **Verify:** Re-read the file to confirm change is in place.

---

### Task 2: Fix wiki query exception log level

**Files:**
- Modify: `app/services/wiki_service.py:89`

On line 89, a broad `except Exception` in `wiki_page_by_lang` logs at `logger.debug`, hiding wiki API failures in production. Should be `logger.warning` since it represents a real failure path (network error, API change, rate limiting).

- [ ] **Change `logger.debug` → `logger.warning` at line 89**

Change in `wiki_page_by_lang`:
```python
            logger.warning("维基百科查询异常: %s", e, exc_info=True)
```

- [ ] **Verify:** Confirm the log level change in the file.

---

### Task 3: Guard `atexit` cleanup against missing globals

**Files:**
- Modify: `app/browser_pool.py:68-81`

The `_cleanup_sync` function called by `atexit` handles the `RuntimeError` from `asyncio.get_running_loop()`, but can crash if `_browser` or `_playwright` were never assigned (e.g., if `get_browser()` was never called). The `_cleanup()` function references the globals and logs on error, but the fallback path in `_cleanup_sync` (`asyncio.new_event_loop()`) re-raises instead of catching. This is a narrow edge case (only fires if atexit runs before first browser init), but the error propagation can mask the real shutdown issue.

- [ ] **Add defensive guard in `_cleanup_sync`**

```python
def _cleanup_sync():
    global _browser, _playwright
    if _browser is None and _playwright is None:
        return
    # ... rest unchanged
```

- [ ] **Verify:** Read the file to confirm the guard is in place.
