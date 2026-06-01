# Phase 2: Medium-Priority Fixes Implementation Plan

> **For agentic workers:** Inline execution — batch 3 self-contained fixes with verification after each.

**Goal:** Fix top 3 remaining medium-priority issues: ThreadPoolExecutor shutdown, callback token replay protection, conditional `--no-sandbox`.

**Architecture:** Each fix is isolated to a single file. No cross-file coordination.

**Priority rationale:**
1. ThreadPoolExecutor shutdown — thread leak risks dropped tasks on process exit (easy fix, clear impact)
2. Callback token replay — TTL-only protection allows repeated trigger of same callback (moderate effort, security)
3. `--no-sandbox` conditional — security hardening for non-Docker environments (easy fix, low risk)

**Not in scope (lower priority / larger effort):**
- `except Exception` tightening (60+ sites, low immediate impact since most already log)
- Pagination abstraction (not blocking, moderate effort)
- `browser_pool.py` split (large refactor, not blocking)
- Test coverage expansion (new initiative, separate plan)

**Tech Stack:** Python, threading, asyncio, HMAC-SHA256, Playwright

---

### Task 1: Add ThreadPoolExecutor shutdown in `JavBusService`

**Files:**
- Modify: `app/services/javbus_service.py:29`

`JavBusService` creates a `ThreadPoolExecutor` at line 29 but never calls `shutdown()`. On process exit, the executor's worker threads may be interrupted mid-task. Add `shutdown(wait=False)` in a cleanup method and register it via atexit.

- [ ] **Add `atexit` import and cleanup method**

At top of file, add import:
```python
import atexit
```

After `self._executor = ThreadPoolExecutor(max_workers=6)`, add:
```python
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        self._executor.shutdown(wait=False)
```

- [ ] **Verify**

Run: `python -c "import ast; ast.parse(open('app/services/javbus_service.py').read()); print('syntax OK')"`
Expected: `syntax OK`

- [ ] **Commit**

```bash
git add app/services/javbus_service.py
git commit -m "feat: add ThreadPoolExecutor shutdown handler in JavBusService"
```

---

### Task 2: Add consume-on-once to callback token resolution

**Files:**
- Modify: `app/secure_callback.py:182-196`

Current `resolve()` checks TTL, signature, and store presence, but never deletes entry after successful resolve. Same callback token can be replayed multiple times. Change `self._store.get(...)` to `self._store.pop(...)` inside the locked section.

- [ ] **Change `resolve()` to consume the entry**

Replace:
```python
        with self._lock:
            stored = self._store.get((prefix, key))
```

With:
```python
        with self._lock:
            stored = self._store.pop((prefix, key), None)
```

And update the "not found" warning message:
```python
            logger.warning(f"Callback not found or already used: {prefix}:{key}")
```

And add `self._dirty = True` after successful pop:
```python
        self._dirty = True
        logger.debug(f"Resolved and consumed callback: {prefix}:{key}")
        return data
```

- [ ] **Verify**

Read `secure_callback.py` to confirm `pop` replaced `get` at resolve.

- [ ] **Commit**

```bash
git add app/secure_callback.py
git commit -m "fix: consume callback token on first resolve to prevent replay"
```

---

### Task 3: Make `--no-sandbox` conditional in browser pool

**Files:**
- Modify: `app/browser_pool.py:43-56`

`--no-sandbox` is hardcoded in the Chromium launch args. This is a security risk outside Docker. Add Docker detection and only include the flag when running inside a container.

- [ ] **Add `_is_docker()` check and conditional flag**

At top of file (after existing `import atexit`):
```python
import os
```

After the stealth comment (line 20 or so):
```python
def _is_docker() -> bool:
    return os.path.exists("/.dockerenv")
```

In the args list, remove `"--no-sandbox"` from the static list and add conditionally:
```python
        if _is_docker():
            args.insert(0, "--no-sandbox")
```

- [ ] **Verify**

Read browser_pool.py to confirm `--no-sandbox` only appears in conditional block.

- [ ] **Commit**

```bash
git add app/browser_pool.py
git commit -m "fix: conditional --no-sandbox (Docker only) for security"
```
