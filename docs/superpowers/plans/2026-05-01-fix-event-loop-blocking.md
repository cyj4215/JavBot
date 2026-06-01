# Fix Event Loop Blocking in query_profile_async

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `ActressService.query_profile_async()` blocking the asyncio event loop by moving sync HTTP calls and `time.sleep()` into thread pool via `asyncio.to_thread()`.

**Architecture:** Extract the synchronous name-resolution block (candidate generation -> find_star -> wiki_aliases -> fuzzy fallback) from `query_profile_async()` into a private `_resolve_name_sync()` method. Wrap the single call in `asyncio.to_thread()`. The RateLimiter stays synchronous (using `threading.Lock`) since it will only run inside thread pool workers now.

**Tech Stack:** Python 3.11, asyncio, telegram.ext

---

### Task 1: Extract `_resolve_name_sync` method

**Files:**
- Modify: `app/service.py:122-163`

- [ ] **Step 1: Add `_resolve_name_sync` private method to `ActressService`**

Insert after `get_rank_cache` at line 120:

```python
    def _resolve_name_sync(self, name: str):
        """Sync name resolution: candidates -> find_star -> wiki aliases -> fuzzy fallback.

        Runs in thread pool via asyncio.to_thread to avoid blocking the event loop.
        """
        candidates = self._name_match_svc.name_candidates(name)
        matched_name, star = self._name_match_svc.find_star(candidates)

        if not star:
            for cand in list(candidates):
                for alias in self._wiki_svc.wiki_aliases(
                    cand,
                    normalize_name_fn=self._name_match_svc._normalize_name,
                    contains_cjk_fn=self._name_match_svc._contains_cjk,
                ):
                    if alias not in candidates:
                        candidates.append(alias)
            matched_name, star = self._name_match_svc.find_star(candidates)

        suggestions: list = []
        if not star:
            seen: set = set()
            for cand in candidates[:4]:
                code, names = self.javbus.fuzzy_search_stars(cand)
                if code != 200 or not names:
                    continue
                for n in names:
                    if n not in seen:
                        seen.add(n)
                        suggestions.append(n)
                    if len(suggestions) >= 10:
                        break
                if len(suggestions) >= 10:
                    break

        return matched_name, star, suggestions
```

- [ ] **Step 2: Replace inline sync block in `query_profile_async` with `asyncio.to_thread` call**

Replace lines 128-163 (from `candidates = self._name_match_svc.name_candidates(name)` through `return result` for the not-found case):

```python
        matched_name, star, suggestions = await asyncio.to_thread(
            self._resolve_name_sync, name
        )

        if not star:
            result = ActressProfile(
                found=False,
                query=name,
                suggestions=suggestions,
            )
            self.profile_cache.set(profile_cache_key, result.__dict__)
            return result
```

- [ ] **Step 3: Run existing tests to verify no regressions**

```bash
python -m pytest tests/test_name_match.py tests/test_cache.py tests/test_formatters.py -v
```

Expected: All existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add app/service.py
git commit -m "fix: move sync name resolution to thread pool in query_profile_async

Extract _resolve_name_sync() and wrap in asyncio.to_thread() to prevent
RateLimiter.time.sleep() and sync HTTP calls from blocking the event loop.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Write unit test for event loop non-blocking

**Files:**
- Create: `tests/test_service_async.py`

- [ ] **Step 1: Write test that verifies `query_profile_async` does not block event loop**

```python
"""Test that query_profile_async does not block the asyncio event loop."""
import asyncio
import time

import pytest


class TestQueryProfileAsync:
    """Verify event loop stays responsive during actress queries."""

    @pytest.mark.asyncio
    async def test_event_loop_not_blocked(self, monkeypatch):
        """A concurrent task should make progress while query_profile_async runs."""
        from app.service import ActressService

        svc = ActressService()

        heartbeat_ticks = []

        async def heartbeat():
            while len(heartbeat_ticks) < 3:
                heartbeat_ticks.append(time.monotonic())
                await asyncio.sleep(0.05)

        query_task = asyncio.create_task(svc.query_profile_async("test_nonexistent_actress_xyz"))
        heartbeat_task = asyncio.create_task(heartbeat())

        done, _ = await asyncio.wait(
            [query_task, heartbeat_task],
            timeout=15.0,
            return_when=asyncio.ALL_COMPLETED,
        )

        assert len(heartbeat_ticks) >= 2, (
            f"Event loop blocked: heartbeat only got {len(heartbeat_ticks)} ticks. "
            "RateLimiter.time.sleep() is likely blocking the main thread."
        )

        assert query_task in done, "query_profile_async did not complete within 15s"
        result = query_task.result()
        assert result.found is False
```

- [ ] **Step 2: Run the test to verify it catches the old bug**

First, temporarily revert the fix to confirm the test detects the problem:
```bash
git stash && python -m pytest tests/test_service_async.py -v -x
```
Expected: FAIL - heartbeat gets < 2 ticks, proving event loop was blocked.

Then restore the fix:
```bash
git stash pop
```

- [ ] **Step 3: Run test with fix in place**

```bash
python -m pytest tests/test_service_async.py -v
```
Expected: PASS - heartbeat gets >= 2 ticks concurrently.

- [ ] **Step 4: Commit**

```bash
git add tests/test_service_async.py
git commit -m "test: add event loop non-blocking test for query_profile_async

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Manual verification checklist

- [ ] **Step 1: Start bot locally and send a search query**

```bash
python -m app.main
```
Send `/s 三上悠亚` in Telegram. Verify:
- Response returns within 5-10 seconds
- No timeout errors in logs
- Other bot commands (`/help`, `/start`) remain responsive during the search

- [ ] **Step 2: Smoke-test other commands**

Verify these still work: `/m`, `/rank`, `/fav`, `/myfav`, `/favlatest`
