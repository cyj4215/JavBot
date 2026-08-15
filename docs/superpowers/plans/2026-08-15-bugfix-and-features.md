# JavBot 缺陷修复与功能完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 4 个真实缺陷（推送去重、磁力代理、搜索历史、作品浏览器），完成 i18n 三语言全覆盖与工程清理，新增推送汇总（digest）、作品详情增强、管理员健康检查三项功能。

**Architecture:** 三层推进：P1 修复层（按用户去重表 `user_seen_works`、MagnetSearch 注入代理、历史记录去重、works 浏览器去切片）→ P2 工程层（i18n 完整化 + 死代码清理 + 回调规范 + 配置统一）→ P3 新功能层（digest 三态推送、作品详情卡、`/admin` 健康检查）。N1 依赖 F1，其余任务独立可 revert。

**Tech Stack:** Python 3.11、python-telegram-bot 21.6、aiomysql（MySQL 8）、Pydantic v2、jvav、curl_cffi、pytest-asyncio、ruff。

**Spec:** `docs/superpowers/specs/2026-08-15-bugfix-and-features-design.md`

**设计偏差说明（相对 spec 的一处微调）：** spec 中 `record_user_work` 签名含 title/date/url/img，但其 DDL 只含 `(user_id, av_id, actress_name)`。本计划按 DDL 落地：`record_user_work(user_id, actress_name, av_id)` 只存去重键；digest 消息所需的作品详情由内存队列持有（Task 10）。

---

## Phase 0: 本地环境准备

### Task 0: 重建 Python 3.11 虚拟环境

**背景**：现有 `.venv` 是 Python 3.13 且无依赖（`jvav` 在 3.13+ 编译失败），单测跑不起来。已验证 `/opt/homebrew/bin/python3.11` 可安装全部依赖。

**Files:**
- Delete: `.venv/`（整个目录）

- [ ] **Step 1: 删除旧 venv 并用 Python 3.11 重建**

```bash
rm -rf .venv
/opt/homebrew/bin/python3.11 -m venv .venv
```

- [ ] **Step 2: 安装依赖并验证关键包可导入**

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "import jvav, pydantic, telegram, aiomysql, curl_cffi, opencc; print('deps OK')"
```

Expected: `deps OK`

- [ ] **Step 3: 安装 mypy（本地静态检查，CI 也需要）**

```bash
.venv/bin/pip install mypy types-requests
```

- [ ] **Step 4: 跑基线单测，确认全部通过**

```bash
.venv/bin/python -m pytest tests/unit/ -q --no-header
```

Expected: 全部 PASS（0 failed）。若有失败先修复环境问题再继续。

- [ ] **Step 5: 跑 lint 基线**

```bash
ruff check app/
```

Expected: 0 errors（如本地 ruff 版本规则差异导致告警，记录但不修复，以 CI 为准）。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore(env): rebuild .venv with Python 3.11"
```

> 注：`.venv` 在 .gitignore 中（若被忽略则只提交 .gitignore 变更或跳过此 commit，改为记录环境重建步骤）。

---

## Phase 1: P1 修复层

### Task 1: F1 — 推送去重改为按用户

**Files:**
- Modify: `app/fav/manager.py`（DDL + `record_user_work` + `cleanup_old_data`）
- Modify: `app/handlers/push.py:60-95`（`check_favorite` 改用 `record_user_work`）
- Test: `tests/unit/test_favorites.py`、`tests/unit/test_handlers_push.py`

- [ ] **Step 1: 写失败测试（按用户去重语义）**

在 `tests/unit/test_favorites.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_record_user_work_new(manager):
    conn = _mock_conn(rowcount=1)
    manager._pool.acquire = _mock_pool_acquire(conn)
    assert await manager.record_user_work(123, "河北彩花", "SSIS-123") is True


@pytest.mark.asyncio
async def test_record_user_work_duplicate(manager):
    conn = _mock_conn(rowcount=0)
    manager._pool.acquire = _mock_pool_acquire(conn)
    assert await manager.record_user_work(123, "河北彩花", "SSIS-123") is False


@pytest.mark.asyncio
async def test_record_user_work_same_av_different_user(manager):
    """同番号不同用户 → 对第二个用户是'新作品'（按用户去重的核心）"""
    conn = _mock_conn(rowcount=1)
    manager._pool.acquire = _mock_pool_acquire(conn)
    assert await manager.record_user_work(456, "河北彩花", "SSIS-123") is True
```

- [ ] **Step 2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_favorites.py -q --no-header
```

Expected: FAIL（`AttributeError: 'FavoritesManager' object has no attribute 'record_user_work'`）

- [ ] **Step 3: manager.py 新增表 DDL**

在 `app/fav/manager.py` 的 `_SQL_INIT` 列表末尾追加：

```python
    """
    CREATE TABLE IF NOT EXISTS user_seen_works (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        av_id VARCHAR(255) NOT NULL,
        actress_name VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_user_av (user_id, av_id),
        INDEX idx_usw_created (created_at)
    )
    """,
```

- [ ] **Step 4: manager.py 新增 record_user_work 方法**

在 `record_actress_work` 方法后面追加：

```python
    async def record_user_work(
        self, user_id: int, actress_name: str, av_id: str
    ) -> bool:
        """按用户记录作品。同一用户第一次见到该番号返回 True，重复返回 False。"""
        try:
            async with self._pool.acquire() as conn, conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT IGNORE INTO user_seen_works (user_id, av_id, actress_name)
                    VALUES (%s, %s, %s)
                    """,
                    (user_id, av_id, actress_name),
                )
                await conn.commit()
                return cur.rowcount > 0  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"记录用户作品失败: {e}")
            return False
```

- [ ] **Step 5: cleanup_old_data 同步清理 user_seen_works**

在 `app/fav/manager.py` 的 `cleanup_old_data` 中，`actress_works` 的 DELETE 之后追加：

```python
                await cur.execute(
                    "DELETE FROM user_seen_works WHERE created_at < %s",
                    (cutoff_works,),
                )
```

- [ ] **Step 6: push.py 改用按用户去重**

在 `app/handlers/push.py` 的 `check_favorite` 内，把：

```python
                            is_new = await favorites_manager.record_actress_work(
                                actress_name=actress_name,
                                av_id=av_id,
                                title=work.title,
                                date=work.date,
                                url=work.url,
                                img=work.img,
                            )
```

替换为：

```python
                            is_new = await favorites_manager.record_user_work(
                                user_id=user_id,
                                actress_name=actress_name,
                                av_id=av_id,
                            )
```

- [ ] **Step 7: 更新 push 测试 mock**

`tests/unit/test_handlers_push.py` 中：
- 第 79 行 `self._fav_mgr.record_actress_work.return_value = True` → `self._fav_mgr.record_user_work.return_value = True`
- 第 113、122、123 行的 `record_actress_work.assert_awaited_once()` → `record_user_work.assert_awaited_once()`
- 第 118 行 `self._fav_mgr.record_actress_work.return_value = False` → `self._fav_mgr.record_user_work.return_value = False`

- [ ] **Step 8: 跑测试确认通过**

```bash
.venv/bin/python -m pytest tests/unit/test_favorites.py tests/unit/test_handlers_push.py -q --no-header
```

Expected: 全部 PASS

- [ ] **Step 9: lint + commit**

```bash
ruff check app/
git add app/fav/manager.py app/handlers/push.py tests/unit/test_favorites.py tests/unit/test_handlers_push.py
git commit -m "fix(push): dedupe new-work pushes per user (user_seen_works)"
```

---

### Task 2: F2 — sukebei 磁力搜索走代理

**Files:**
- Modify: `app/service.py:104-109`（注入 `magnet_search_module`）
- Modify: `app/services/javbus_service.py:113`（用注入实例）
- Test: `tests/unit/test_service.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_service.py` 追加：

```python
class TestMagnetSearchInjection:
    """Proxy-configured MagnetSearch must be wired into JavBusService."""

    def test_magnet_search_injected(self):
        """ActressService 构造时把带代理的 MagnetSearch 注入 JavBusService。"""
        s = ActressService()
        assert s._javbus_svc._magnet_search is s._magnet_search

    @pytest.mark.asyncio
    async def test_get_av_magnets_uses_injected_instance(self):
        """get_av_magnets 使用注入的实例，而非新建无代理实例。"""
        s = ActressService()
        s.javbus.get_av_magnets = MagicMock(return_value=(200, []))
        s._javbus_svc._javbus_limiter = MagicMock()  # 避免真实限流 sleep
        fake = MagicMock()
        fake.search = MagicMock(
            return_value=[
                MagnetLink(title="T", magnet="magnet:?xt=urn:btih:abc", size="1G")
            ]
        )
        s._javbus_svc._magnet_search = fake
        result = s._javbus_svc.get_av_magnets("SSIS-123", 2)
        fake.search.assert_called_once_with("SSIS-123", 2, 20)
        assert len(result) == 1
```

- [ ] **Step 2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_service.py::TestMagnetSearchInjection -q --no-header
```

Expected: FAIL（`assert s._javbus_svc._magnet_search is s._magnet_search` — 目前 `_magnet_search` 为 None 或不同实例）

- [ ] **Step 3: service.py 注入**

`app/service.py` 的 `JavBusService` 构造处追加参数：

```python
        self._javbus_svc = javbus_service or JavBusService(
            javbus_util=self.javbus,
            av_meta_cache=self.av_meta_cache,
            javbus_limiter=self._javbus_limiter,
            uncensored=uncensored,
            magnet_search_module=self._magnet_search,
        )
```

- [ ] **Step 4: javbus_service.py 使用注入实例**

`app/services/javbus_service.py` 的 `get_av_magnets` 中，把：

```python
        sukebei_magnets = MagnetSearch().search(av_id, max(0, limit - len(javbus_magnets)), 20)
```

替换为：

```python
        magnet_search = self._magnet_search if self._magnet_search is not None else MagnetSearch()
        sukebei_magnets = magnet_search.search(
            av_id, max(0, limit - len(javbus_magnets)), 20
        )
```

- [ ] **Step 5: 跑测试确认通过**

```bash
.venv/bin/python -m pytest tests/unit/test_service.py -q --no-header
```

Expected: 全部 PASS

- [ ] **Step 6: lint + commit**

```bash
ruff check app/
git add app/service.py app/services/javbus_service.py tests/unit/test_service.py
git commit -m "fix(magnet): inject proxy-configured MagnetSearch into JavBusService"
```

---

### Task 3: F3 — /history 记录所有搜索 + 24h 去重

**Files:**
- Modify: `app/fav/manager.py:16-17,311-335`（去重语义）
- Modify: `app/fav/__init__.py`（常量导出）
- Modify: `app/handlers/search.py`（`run_search_reply` 记录）
- Modify: `app/handlers/magnet.py`（`run_magnet_reply` 记录 + `user_id` 参数）
- Modify: `app/handlers/common.py:305-329`（`callback_magnet` 传 user_id）
- Modify: `app/handlers/history.py:53-59`（番号路由到磁力按钮）
- Test: `tests/unit/test_favorites.py`、`tests/unit/test_handlers_search.py`

- [ ] **Step 1: 写失败测试（24h 去重）**

在 `tests/unit/test_favorites.py` 追加：

```python
@pytest.mark.asyncio
async def test_record_favorite_query_dedup_skip(manager):
    """24h 内同用户同名字已有记录 → 跳过。"""
    manager._select_one = AsyncMock(return_value={"val": 1})
    assert await manager.record_favorite_query(123, "河北彩花") is False


@pytest.mark.asyncio
async def test_record_favorite_query_insert(manager):
    """无重复记录 → 插入并返回 True。"""
    manager._select_one = AsyncMock(return_value=None)
    manager._execute = AsyncMock(return_value=1)
    assert await manager.record_favorite_query(123, "河北彩花") is True
```

- [ ] **Step 2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_favorites.py::test_record_favorite_query_dedup_skip -q --no-header
```

Expected: FAIL（现实现是频率上限：`_select_one` 返回 count，未达上限也会继续插入）

- [ ] **Step 3: manager.py 改去重语义**

`app/fav/manager.py` 顶部常量替换：

```python
QUERY_FREQUENCY_LIMIT = 10
QUERY_FREQUENCY_WINDOW = 3600
```

→

```python
QUERY_DEDUP_WINDOW = 86400  # 同一用户同一名字 24h 内只记录一次
```

`record_favorite_query` 整体替换为：

```python
    async def record_favorite_query(self, user_id: int, actress_name: str) -> bool:
        """记录一次搜索。同用户同名字 24h 内已有记录则跳过（去重）。"""
        try:
            window_start = (datetime.now() - timedelta(seconds=QUERY_DEDUP_WINDOW)).isoformat()
            existing = await self._select_one(
                """
                SELECT 1 AS val FROM favorite_queries
                WHERE user_id = %s AND actress_name = %s AND query_time > %s
                LIMIT 1
                """,
                (user_id, actress_name, window_start),
            )
            if existing:
                return False
            await self._execute(
                "INSERT INTO favorite_queries (user_id, actress_name) VALUES (%s, %s)",
                (user_id, actress_name),
            )
            return True
        except Exception as e:
            logger.error(f"记录查询历史失败: {e}")
            return False
```

同时删除 `_is_query_rate_limited` 方法（不再使用）。

- [ ] **Step 4: 更新 fav/__init__.py 导出**

`app/fav/__init__.py`：

```python
from .manager import FavoritesManager, get_favorites_manager

__all__ = [
    "FavoritesManager",
    "get_favorites_manager",
]
```

> 注：`QUERY_FREQUENCY_LIMIT`/`QUERY_FREQUENCY_WINDOW` 已无引用（`app/fav/push.py` 会在 Task 6 删除）。

- [ ] **Step 5: 写失败测试（搜索后记录历史）**

在 `tests/unit/test_handlers_search.py` 追加：

```python
class TestRunSearchReplyRecordsHistory:
    """run_search_reply 成功后记录搜索历史。"""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        import app.handlers.search as search_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_user_language.return_value = "zh_CN"
        self._fav_mgr.is_favorite = AsyncMock(return_value=False)
        self._fav_mgr.record_favorite_query = AsyncMock(return_value=True)
        self._fav_mgr.increment_stat = AsyncMock()
        monkeypatch.setattr(
            search_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr)
        )
        self._svc = shared_global.service
        self._svc.query_profile_async.return_value = ActressProfile(
            found=True, query="三上悠亜", star_name="三上悠亜", star_id="X"
        )
        shared_global.config.send_latest_covers = False

    @pytest.mark.asyncio
    async def test_records_query_after_success(self, mock_msg):
        from app.handlers.search import run_search_reply
        await run_search_reply(mock_msg, "三上悠亜", user_id=12345)
        self._fav_mgr.record_favorite_query.assert_awaited_once_with(12345, "三上悠亜")
```

- [ ] **Step 6: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_handlers_search.py::TestRunSearchReplyRecordsHistory -q --no-header
```

Expected: FAIL（`record_favorite_query` 未被调用，`assert_awaited_once_with` 报错）

- [ ] **Step 7: search.py 记录历史**

`app/handlers/search.py`：
1. 顶部 import 追加：`from ..services.text_utils import normalize_name`
2. `run_search_reply` 中，`is_fav` 判断块之后追加：

```python
        if user_id is not None:
            try:
                await fav_mgr.record_favorite_query(user_id, normalize_name(query))
            except Exception:
                logging.getLogger(__name__).debug("记录搜索历史失败", exc_info=True)
```

- [ ] **Step 8: magnet.py 记录番号搜索**

`app/handlers/magnet.py`：
1. 顶部 import 追加：`from ..services.text_utils import normalize_name`
2. `run_magnet_reply` 签名改为：

```python
async def run_magnet_reply(
    msg: Message, query: str, shared=None, user_id: int | None = None
) -> None:
```

3. 其中统计块替换为：

```python
    from ..fav import get_favorites_manager

    try:
        fav_mgr = await get_favorites_manager()
        await fav_mgr.increment_stat("total_magnet_searches")
        if user_id is not None:
            await fav_mgr.record_favorite_query(user_id, normalize_name(query))
    except Exception:
        pass
```

- [ ] **Step 9: 更新 run_magnet_reply 的三个调用点**

1. `app/handlers/magnet.py` 的 `magnet_cmd`：

```python
    user = update.effective_user
    await run_magnet_reply(msg, query, shared=shared, user_id=user.id if user else None)
```

2. `app/handlers/search.py` 的 `on_text` 整体替换为：

```python
@require_auth
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared) -> None:
    from .magnet import run_magnet_reply

    if not msg.text:
        return

    query: str = msg.text.strip()
    if not query:
        return

    user: Any | None = update.effective_user
    user_id = user.id if user else None
    if looks_like_av_id(query):
        await run_magnet_reply(msg, query, shared=shared, user_id=user_id)
        return

    await run_search_reply(msg, query, user_id, shared=shared)
```

3. `app/handlers/common.py` 的 `callback_magnet`：

```python
    await q.answer(f"🧲 {query}")
    user_id: int | None = update.effective_user.id if update.effective_user else None
    await run_magnet_reply(cast(Message, q.message), query, shared=shared, user_id=user_id)
```

- [ ] **Step 10: history.py 番号路由到磁力按钮**

`app/handlers/history.py` 顶部 import 追加：

```python
from ..formatters import looks_like_av_id
```

`_render_history_page` 中按钮构建块替换为：

```python
    keyboard = []
    for q in page_queries:
        name = q["actress_name"]
        btn_label = name[:14] + "…" if len(name) > 14 else name
        prefix = "magnet" if looks_like_av_id(name) else "search"
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🔍 {btn_label}", callback_data=_short_callback(prefix, name)
                )
            ]
        )
```

- [ ] **Step 11: 跑全部相关测试**

```bash
.venv/bin/python -m pytest tests/unit/test_favorites.py tests/unit/test_handlers_search.py tests/unit/test_handlers_history.py -q --no-header
```

Expected: 全部 PASS（history 测试的 `_render_history_page` 签名未变，仍兼容）

- [ ] **Step 12: lint + commit**

```bash
ruff check app/
git add app/fav/manager.py app/fav/__init__.py app/handlers/search.py app/handlers/magnet.py app/handlers/common.py app/handlers/history.py tests/unit/test_favorites.py tests/unit/test_handlers_search.py
git commit -m "fix(history): record all searches with 24h dedup, route AV IDs to magnet"
```

---

### Task 4: F4 — works 浏览器去掉 3 条上限

**Files:**
- Modify: `app/handlers/works.py:138`（删除 `works = works[:3]`）
- Test: `tests/unit/test_works_browser.py`

- [ ] **Step 1: 写失败测试（完整列表可翻页）**

`tests/unit/test_works_browser.py` 中，把第 85-92 行附近模拟 3 条上限的测试替换为：

```python
    def test_full_list_no_cap(self):
        """浏览器基于完整合并列表翻页，不受 3 条硬编码限制。"""
        works = [_make_work(f"A-{i:03d}") for i in range(10)]
        caption, keyboard, _ = _build_works_page(works, "Test", 5, _t)
        assert "A-006" in caption
        assert "works_page:6:10" in caption
        assert keyboard is not None
```

并在文件末尾追加回调级测试：

```python
class TestWorksCallbackFullList:
    """works_callback 把完整列表传给翻页器（不再截断为 3）。"""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global):
        from app.handlers.works import works_callback
        self._handler = works_callback
        profile = ActressProfile(
            found=True, query="T", star_name="Test", star_id="T-1",
            latest_works=[MergedWork(id=f"A-{i:03d}", img="") for i in range(10)],
        )
        shared_global.service.query_profile_async.return_value = profile

    @pytest.mark.asyncio
    async def test_browses_beyond_three_works(self, mock_update, mock_context, mock_q):
        from app.secure_callback import short_callback
        mock_q.data = short_callback("works", "Test|8")
        mock_update.callback_query = mock_q
        await self._handler(mock_update, mock_context)
        text = mock_q.edit_message_text.call_args[0][0]
        assert "A-009" in text
```

同时补 import：

```python
from app.models import ActressProfile, MergedWork
```

- [ ] **Step 2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_works_browser.py -q --no-header
```

Expected: FAIL（`test_browses_beyond_three_works` 断言 "A-009" 不在文本中——被 `[:3]` 截断）

- [ ] **Step 3: 删除硬编码切片**

`app/handlers/works.py` 的 `works_callback` 中删除：

```python
    works = works[:3]
```

（保留 `works = await _get_profile_works(star_name, shared)` 一行）

- [ ] **Step 4: 跑测试确认通过**

```bash
.venv/bin/python -m pytest tests/unit/test_works_browser.py -q --no-header
```

Expected: 全部 PASS

- [ ] **Step 5: lint + commit**

```bash
ruff check app/
git add app/handlers/works.py tests/unit/test_works_browser.py
git commit -m "fix(works): browse full merged works list, drop hardcoded 3-item cap"
```

---

## Phase 2: P2 工程层

### Task 5: E1 — i18n 完整化（三语言全覆盖）

**Files:**
- Create: `tests/unit/test_i18n_coverage.py`
- Modify: `app/services/i18n/zh_CN.py`、`en_US.py`、`ja_JP.py`（新增 key，见下表）
- Modify: `app/handlers/stats.py`、`common.py`、`magnet.py`、`favorites.py`、`push.py`、`history.py`、`works.py`、`search.py`
- Modify: `tests/unit/test_handlers_history.py`（`_render_history_page` 传 `_t` stub）

- [ ] **Step 1: 写回归测试（handler 用到的 key 必须三语言齐全）**

创建 `tests/unit/test_i18n_coverage.py`：

```python
"""Regression: every i18n key used in handlers exists in all three languages."""
import re
from pathlib import Path

from app.services.i18n import _TRANSLATIONS, SUPPORTED_LANGUAGES

HANDLERS_DIR = Path(__file__).resolve().parents[2] / "app" / "handlers"

_KEY_RE = re.compile(r"""_(?:t)?\(['"]([a-z_][a-z0-9_]*)['"]""")


def test_all_handler_keys_translated():
    missing = set()
    for path in sorted(HANDLERS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for key in _KEY_RE.findall(text):
            if key not in _TRANSLATIONS:
                missing.add(f"{path.name}:{key}")
    assert not missing, f"Untranslated keys: {sorted(missing)}"


def test_all_keys_have_all_languages():
    for key, langs in _TRANSLATIONS.items():
        for lang in SUPPORTED_LANGUAGES:
            assert langs.get(lang, "").strip(), f"{key}[{lang}] is empty"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_i18n_coverage.py -q --no-header
```

Expected: FAIL（`Untranslated keys: [...]`——handler 里全是硬编码，无 `_t` 引用，且缺 key 时 `_t` 返回 key 本身；同时部分 key 三语言缺失）

- [ ] **Step 3: 三个语言文件补齐新 key**

在 `app/services/i18n/zh_CN.py`、`en_US.py`、`ja_JP.py` 的 `TRANSLATIONS` dict 末尾追加以下 key（三份文件的 key 完全一致，仅译文不同）：

| key | zh_CN | en_US | ja_JP |
|-----|-------|-------|-------|
| `magnet_loading` | 正在查询，请稍等... | Searching, please wait... | 検索中、お待ちください... |
| `magnet_searching` | 正在搜索磁力，请稍等... | Searching for magnets, please wait... | マグネットを検索中、お待ちください... |
| `fav_latest_querying` | 正在查询 {} 位收藏女优的最新作品... | Checking latest works of {} favorite actresses... | お気に入りの{}名の最新作品を確認中... |
| `fav_latest_empty` | 暂无最新作品信息。 | No latest work information. | 最新作品情報はありません。 |
| `fav_latest_failed` | 查询失败，请稍后再试。 | Query failed, please try again later. | 検索に失敗しました。後でもう一度お試しください。 |
| `fav_favlatest_title` | 🎬 收藏女优最新作品 | 🎬 Latest Works of Favorites | 🎬 お気に入りの最新作品 |
| `fav_unknown_actress` | 未知 | Unknown | 不明 |
| `fav_unknown_date` | 未知日期 | Unknown date | 日付不明 |
| `fav_more_works` | ...还有 {} 部作品 | ...and {} more works | ...他{}作品 |
| `fav_add_failed_alert` | 收藏失败 | Failed to add favorite | お気に入り追加に失敗しました |
| `fav_remove_failed_alert` | 取消收藏失败 | Failed to remove favorite | お気に入り削除に失敗しました |
| `push_status_on` | ✅ 已开启 | ✅ Enabled | ✅ 有効 |
| `push_status_off` | ❌ 已关闭 | ❌ Disabled | ❌ 無効 |
| `push_status` | 📰 新作品推送状态：{}\n\n使用 /push on 开启推送\n使用 /push off 关闭推送 | 📰 New work push status: {}\n\nUse /push on to enable\nUse /push off to disable | 📰 新作プッシュ状態：{}\n\n/push on で有効化\n/push off で無効化 |
| `push_enabled_msg` | ✅ 已开启新作品推送\n\n当你关注的女优有新作品时，我会及时通知你！ | ✅ Push notifications enabled.\n\nI'll notify you when your favorite actresses release new works! | ✅ 新作プッシュを有効にしました。\n\nお気に入りの新作をすぐお知らせします！ |
| `push_disabled_msg` | ❌ 已关闭新作品推送 | ❌ Push notifications disabled | ❌ 新作プッシュを無効にしました |
| `push_usage` | 用法：/push [on\|off] | Usage: /push [on\|off] | 使い方：/push [on\|off] |
| `push_title` | 🎉 关注女优更新啦！ | 🎉 Your favorite actress has a new work! | 🎉 お気に入りの新作が出ました！ |
| `push_actress` | 👩 女优： | 👩 Actress: | 👩 女優： |
| `push_av_id` | 🎬 番号： | 🎬 AV ID: | 🎬 品番： |
| `push_date` | 📅 日期： | 📅 Date: | 📅 日付： |
| `push_title_label` | 📝 标题： | 📝 Title: | 📝 タイトル： |
| `push_unknown` | 未知 | Unknown | 不明 |
| `push_query_btn` | 👩 查询 {} | 👩 Query {} | 👩 {} を検索 |
| `history_total` | 共 {} 条记录 | {} entries in total | 全{}件 |
| `history_hint` | <i>点击按钮重新查询</i> | <i>Click a button to search again</i> | <i>ボタンをクリックして再検索</i> |
| `search_cancel_btn` | ⏹ 取消 | ⏹ Cancel | ⏹ キャンセル |
| `search_cancel_done` | ⏹ 已取消查询 | ⏹ Search cancelled | ⏹ 検索をキャンセルしました |
| `search_cancel_denied` | 无权取消他人的查询 | You cannot cancel another user's search | 他人の検索をキャンセルできません |
| `search_none_running` | 没有正在进行的查询 | No search in progress | 実行中の検索はありません |
| `stat_total_searches` | 🔍 搜索次数 | 🔍 Searches | 🔍 検索回数 |
| `stat_profiles_viewed` | 👩 查看女优资料 | 👩 Profiles Viewed | 👩 プロフィール表示 |
| `stat_magnet_searches` | 🧲 磁力搜索次数 | 🧲 Magnet Searches | 🧲 マグネット検索 |
| `stat_favorites_added` | ⭐ 收藏次数 | ⭐ Favorites Added | ⭐ お気に入り追加 |
| `stat_favorites_removed` | 💔 取消收藏次数 | 💔 Favorites Removed | 💔 お気に入り削除 |

> 复用已有 key（不新增）：`magnet_usage`、`fav_added`、`fav_removed`、`fav_found`、`fav_add_failed`、`fav_remove_failed`、`fav_expired`、`menu_return`、`fav_page_info`、`search_magnet_for`、`search_cancelled`、`no_permission`、`no_permission_alert`、`error_generic`。

- [ ] **Step 4: stats.py 改用 i18n**

`app/handlers/stats.py` 删除 `_STAT_LABELS`、`_STAT_LABELS_EN`、`_STAT_LABELS_JA`、`_labels_for_lang`，`stats_cmd` 改为：

```python
_STAT_KEYS = [
    ("total_searches", "stat_total_searches"),
    ("total_profiles_viewed", "stat_profiles_viewed"),
    ("total_magnet_searches", "stat_magnet_searches"),
    ("total_favorites_added", "stat_favorites_added"),
    ("total_favorites_removed", "stat_favorites_removed"),
]


@require_auth
async def stats_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared
) -> None:
    lang = await _get_lang(shared, update)

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    fav_mgr = await get_favorites_manager()
    stats = await fav_mgr.get_all_stats()

    if not stats:
        await msg.reply_text(_("stats_title"))
        return

    lines = [f"<b>📊 {_('stats_title')}</b>", ""]
    for stat_key, label_key in _STAT_KEYS:
        val = stats.get(stat_key, 0)
        lines.append(f"{_(label_key)}: <code>{val}</code>")

    await msg.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )
```

- [ ] **Step 5: common.py 权限提示走 i18n**

`app/handlers/common.py`：
1. `require_auth` 内 `await msg.reply_text("无权限使用此机器人。")` → `await msg.reply_text(shared.service.i18n.t("no_permission"))`
2. `require_auth_callback` 内 `await q.answer("无权限使用", show_alert=True)` → `await q.answer(shared.service.i18n.t("no_permission_alert"), show_alert=True)`

- [ ] **Step 6: magnet.py 文案走 i18n**

`app/handlers/magnet.py` 的 `run_magnet_reply`：
1. `waiting = await msg.reply_text("正在查询，请稍等...")` → `waiting = await msg.reply_text(_("magnet_loading"))`
2. `await waiting.edit_text("正在搜索磁力，请稍等...")` → `await waiting.edit_text(_("magnet_searching"))`
3. `magnet_cmd` 的用法提示 `await msg.reply_text("用法：/search 关键词\n例如：/search SSIS-123")` → 先取语言再 `await msg.reply_text(_("magnet_usage"))`（`magnet_cmd` 内加 `from .common import make_t`，`_ = await make_t(shared, update)`）

- [ ] **Step 7: favorites.py 文案走 i18n**

`app/handlers/favorites.py`：
1. `favorites_latest_cmd`：`await msg.reply_text(f"正在查询 {len(favorites)} 位收藏女优的最新作品...")` → `await msg.reply_text(_("fav_latest_querying", len(favorites)))`；`await waiting.edit_text("暂无最新作品信息。")` → `_("fav_latest_empty")`；`"<b>🎬 收藏女优最新作品</b>"` → `f"<b>{_('fav_favlatest_title')}</b>"`；`html.escape(work.get("actress_name", "未知"))` → `html.escape(work.get("actress_name") or _("fav_unknown_actress"))`；`work.get("date", "未知日期")` → `work.get("date") or _("fav_unknown_date")`；`f"...还有 {n} 部作品"` → `_("fav_more_works", n)`；`await waiting.edit_text("查询失败，请稍后再试。")` → `_("fav_latest_failed")`
2. `callback_favnow`：`await q.answer(f"未找到女优: {actress_name}", show_alert=True)` → `await q.answer(_("fav_found", actress_name), show_alert=True)`；`await q.answer(f"✅ 已收藏: {profile.star_name}")` → `await q.answer(_("fav_added", profile.star_name))`；`await q.answer("收藏失败", show_alert=True)` → `await q.answer(_("fav_add_failed_alert"), show_alert=True)`
3. `callback_unfavnow`：`await q.answer(f"✅ 已取消收藏: {actress_name}")` → `await q.answer(_("fav_removed", actress_name))`；`await q.answer("取消收藏失败", show_alert=True)` → `await q.answer(_("fav_remove_failed_alert"), show_alert=True)`
4. 两处 `q.answer(f"正在查询 {actress_name}...")`（`callback_favquery`）与 `q.answer(f"已收藏: ...")` 的中间态提示保持现状（动态内容，无模板，不违反规范）；但 `callback_favquery` 的 `_("fav_expired")` 已存在，无需改。

> 注意：`callback_favnow`/`callback_unfavnow` 中 `_` 需要在函数开头定义（`_ = await make_t(shared, update)`），若原来没有则补上。

- [ ] **Step 8: push.py 通知模板走 i18n**

`app/handlers/push.py` 的 `send_new_work_notification` 中：

```python
        lines = [
            f"<b>{_('push_title')}</b>",
            "",
            f"<b>{_('push_actress')}</b>{html.escape(actress_name)}",
            f"<b>{_('push_av_id')}</b><code>{html.escape(av_id)}</code>",
        ]
        if av_date != _("push_unknown"):
            lines.append(f"<b>{_('push_date')}</b>{html.escape(av_date)}")
        if av_title:
            lines.append(f"<b>{_('push_title_label')}</b>{html.escape(av_title[:80])}")
```

`av_id = work.id or _("push_unknown")`、`av_date = work.date or _("push_unknown")`；按钮文案：`_("search_magnet_for", av_id)`（已有）、`_("push_query_btn", actress_name)`。

`push_toggle_cmd`：
1. 状态行：`settings.get("push_enabled", True)` → 用 `_("push_status_on") if enabled else _("push_status_off")`，拼 `_("push_status", status)`；先定义 `_ = await make_t(shared, update)`
2. `await msg.reply_text("✅ 已开启新作品推送\n\n当你关注的女优有新作品时，我会及时通知你！")` → `_("push_enabled_msg")`
3. `await msg.reply_text("❌ 已关闭新作品推送")` → `_("push_disabled_msg")`
4. `await msg.reply_text("用法：/push [on|off]")` → `_("push_usage")`

- [ ] **Step 9: history.py 文案走 i18n + 测试更新**

`app/handlers/history.py` 的 `_render_history_page` 签名改为：

```python
def _render_history_page(
    queries: list[dict],
    page: int,
    total: int,
    _t=lambda k, *a: k,
) -> tuple[str, InlineKeyboardMarkup]:
```

内部文案替换：`"<b>📜 最近搜索</b>"` → `f"<b>{_t('history_title')}</b>"`；`f"共 {total} 条记录"` → `_t("history_total", total)`；`f"第 {page}/{total_pages} 页"` → `_t("fav_page_info", page, total_pages)`；`"<i>点击按钮重新查询</i>"` → `_t("history_hint")`；`"🔄 返回主菜单"` → `_t("menu_return")`。`history_cmd` 中调用处传 `_`（先 `_ = await make_t(shared, update)`），空历史提示 `_("history_empty")`。

`tests/unit/test_handlers_history.py`：`TestRenderHistoryPage` 的所有 `_render_history_page(...)` 调用改为传入 stub 并调整断言（参照 `tests/unit/test_works_browser.py` 的 `_t` stub 风格）：

```python
    def _t(self, key, *args):
        if args:
            return f"{key}:{':'.join(str(a) for a in args)}"
        return key
```

- `test_empty_queries`：`assert "history_title" in text`；`assert "history_total:0" in text`
- `test_single_page`：`assert "history_total:5" in text`
- `test_pagination_buttons_appear` / `test_page_2`：`assert "fav_page_info:1:2" in text` / `"fav_page_info:2:2"`
- 其余按钮类断言（`▶️`/`◀️`/`menu:search`）不变

- [ ] **Step 10: works.py / search.py 文案走 i18n**

1. `app/handlers/works.py` 的 `works_callback`：顶部 import 追加 `from .common import make_t, require_auth_callback`（把现有 `from .common import require_auth_callback` 替换）；在 `_resolve_callback("works", data)` 之前先取语言：

```python
    data = q.data or ""
    lang = await _get_lang(shared, update)

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    raw = _resolve_callback("works", data)
    if raw is None:
        await q.answer(_("fav_expired"), show_alert=True)
        return
```

（删除原第 125-128 行重复的 lang 获取块，`_get_lang` 从 `.common` import）
2. `app/handlers/search.py` 的 `cancel_search_callback`：函数开头定义 `_ = await make_t(shared, update)`；`"该操作已过期"` → `_("fav_expired")`；`"无权取消他人的查询"` → `_("search_cancel_denied")`；`"已取消"` → `_("search_cancelled")`；`"⏹ 已取消查询"` → `_("search_cancel_done")`；`"没有正在进行的查询"` → `_("search_none_running")`；`run_search_reply` 的取消按钮 `"⏹ 取消"` → `_("search_cancel_btn")`

- [ ] **Step 11: 全量跑测试**

```bash
.venv/bin/python -m pytest tests/unit/ -q --no-header
```

Expected: 全部 PASS（含新增 `test_i18n_coverage.py`；若原有测试断言了被迁移的硬编码字符串且 zh 译文与之相同则无需改动，否则按 Step 9 的方式适配）

- [ ] **Step 12: lint + commit**

```bash
ruff check app/
git add app/services/i18n/ app/handlers/ tests/unit/
git commit -m "feat(i18n): full 3-language coverage for all handler strings + regression test"
```

---

### Task 6: E2 — 死代码清理

**Files:**
- Delete: `app/session.py`、`app/fav/push.py`、`app/fav/export.py`
- Modify: `app/service.py:20,63`（移除 BotSession 引用）
- Modify: `app/fav/__init__.py`

- [ ] **Step 1: 确认无引用**

```bash
grep -rn "BotSession\|PushService\|FavoriteExportService\|session\." app/ tests/ --include="*.py" | grep -v "\.venv" | grep -v "fav/push.py\|fav/export.py\|session.py"
```

Expected: 仅剩 `app/service.py` 的 `from .session import BotSession` 与 `self._bot_session = BotSession(proxy_addr)` 两行（Task 2 已把 `_magnet_search` 转为依赖，不在删除之列）。

- [ ] **Step 2: service.py 移除 BotSession**

`app/service.py`：
1. 删除第 20 行 `from .session import BotSession`
2. 删除第 63 行 `self._bot_session = BotSession(proxy_addr)`

- [ ] **Step 3: 删除三个文件并更新 fav/__init__.py**

```bash
rm app/session.py app/fav/push.py app/fav/export.py
```

`app/fav/__init__.py` 内容（Task 3 已更新过，确认最终为）：

```python
from .manager import FavoritesManager, get_favorites_manager

__all__ = [
    "FavoritesManager",
    "get_favorites_manager",
]
```

- [ ] **Step 4: 全量跑测试 + import 冒烟**

```bash
.venv/bin/python -m pytest tests/unit/ -q --no-header
.venv/bin/python -c "import app.main; print('import OK')"
```

Expected: 全部 PASS；`import OK`

- [ ] **Step 5: lint + commit**

```bash
ruff check app/
git add -A
git commit -m "refactor: remove dead code (BotSession, PushService, FavoriteExportService)"
```

---

### Task 7: E3 — rank 回调解析统一 + 安全规范说明

**Files:**
- Modify: `app/handlers/rank.py:159-216`（合并 `rank:` / `rank_retry:` 解析）
- Modify: `app/secure_callback.py:1-10`（docstring 补安全规范）

- [ ] **Step 1: 写失败测试（统一解析）**

创建 `tests/unit/test_rank_callback_parse.py`：

```python
"""rank callback 解析：rank: / rank_retry: 统一正则。"""
import re

_PATTERN = re.compile(r"^rank(?:_retry)?:(\d{1,2}):(\d)(?::([01]))?$")


def _parse(data: str):
    m = _PATTERN.match(data)
    if not m:
        return None
    return {
        "limit": int(m.group(1)),
        "page": int(m.group(2)),
        "with_avatars": m.group(3) == "1" if m.group(3) is not None else False,
        "is_retry": data.startswith("rank_retry:"),
    }


def test_rank_normal():
    assert _parse("rank:20:1:0") == {
        "limit": 20, "page": 1, "with_avatars": False, "is_retry": False,
    }


def test_rank_with_avatars():
    assert _parse("rank:20:2:1")["with_avatars"] is True


def test_rank_retry():
    assert _parse("rank_retry:20:3") == {
        "limit": 20, "page": 3, "with_avatars": False, "is_retry": True,
    }


def test_rank_retry_no_avatars_group():
    assert _parse("rank_retry:10:1")["with_avatars"] is False


def test_invalid():
    assert _parse("rank:abc:1") is None
    assert _parse("other:1") is None
```

- [ ] **Step 2: 跑测试确认通过（正则先行落地）**

```bash
.venv/bin/python -m pytest tests/unit/test_rank_callback_parse.py -q --no-header
```

Expected: PASS（此测试独立于 handler，先锁定解析语义）

- [ ] **Step 3: 重构 rank_page_callback**

`app/handlers/rank.py` 中 `rank_page_callback` 的整个主体（从 `data = q.data or ""` 到函数末尾）替换为：

```python
    data = q.data or ""

    m = re.match(r"^rank(?:_retry)?:(\d{1,2}):(\d)(?::([01]))?$", data)
    if not m:
        await q.answer()
        return

    limit = int(m.group(1))
    page = int(m.group(2))
    limit = max(1, min(limit, 50))
    page = max(1, min(page, 5))
    is_retry = data.startswith("rank_retry:")
    with_avatars = m.group(3) == "1" if m.group(3) is not None else False

    await q.answer(_("rank_retrying") if is_retry else _("rank_loading"))
    try:
        stars = await shared.service.get_hot_star_rankings(limit, page)
        await _send_rank_result(
            q,
            stars,
            limit,
            page,
            with_avatars=with_avatars,
            is_edit=True,
            msg=q.message,
            _t=_,
            shared=shared,
        )
    except Exception as exc:
        logger.exception("rank callback failed: %s", exc)
        await _handle_rank_error(q, limit, page, is_edit=True, _t=_)
```

> 注：retry 场景 `with_avatars=False`，与原行为一致；`msg=q.message` 仅在 with_avatars 时被使用，无副作用。

- [ ] **Step 4: secure_callback.py docstring 补安全规范**

`app/secure_callback.py` 模块 docstring 末尾追加：

```
Callback security rules:
- SIGNED callbacks (short_callback/resolve_callback) MUST be used for anything
  carrying user data or query content (search queries, actress names, AV IDs,
  magnet links, user IDs). Tokens are single-use and expire after 7 days.
- PLAIN callbacks are allowed ONLY for UI navigation with no sensitive data
  (menu:, lang:, hist:page:, rank:, rank_retry:, pushmode:). Never put user
  data or query strings into a plain callback.
```

- [ ] **Step 5: 全量跑测试**

```bash
.venv/bin/python -m pytest tests/unit/ -q --no-header
```

Expected: 全部 PASS（rank 相关测试 `test_handlers_common.py` 中的 `menu:rank` 路径不受影响；`tests/unit/test_rank_service.py` 不受影响）

- [ ] **Step 6: lint + commit**

```bash
ruff check app/
git add app/handlers/rank.py app/secure_callback.py tests/unit/test_rank_callback_parse.py
git commit -m "refactor(rank): unify rank/rank_retry callback parsing, document callback security rules"
```

---

### Task 8: E5 — 小修（配置统一）

**Files:**
- Modify: `app/config.py`（`push_batch_delay`、`magnet_cache_ttl`）
- Modify: `app/main.py`（传给 ActressService）
- Modify: `app/service.py`（构造参数）
- Modify: `app/services/rank_service.py:56`（预热用默认 limit）
- Modify: `app/magnet_search.py:19-21,30`（cache_ttl 参数化）
- Modify: `app/handlers/push.py:126`（batch delay 可配置）
- Modify: `.env.example`
- Modify: `tests/conftest.py`（mock_config 补字段）

- [ ] **Step 1: config.py 新增字段**

`app/config.py` 的 `BotConfig` 增加两个字段：

```python
    push_batch_delay: int
    magnet_cache_ttl: int
```

`from_env()` 中：

```python
            push_batch_delay=_env_int("PUSH_BATCH_DELAY", "5"),
            magnet_cache_ttl=_env_int("MAGNET_CACHE_TTL", "300"),
```

- [ ] **Step 2: service.py / magnet_search.py / rank_service.py 参数化**

1. `app/service.py` 的 `ActressService.__init__` 增加参数 `magnet_cache_ttl: int = 300`、`rank_limit_default: int = 20`，并：
   - `self._magnet_search = MagnetSearch(proxy_addr, cache_ttl=magnet_cache_ttl)`
   - `self._rank_svc = RankService(rank_cache=..., refresh_interval=rank_cache_ttl, javdb_scraper=..., default_limit=rank_limit_default)`
2. `app/magnet_search.py`：

```python
    def __init__(self, proxy: str = "", cache_ttl: int | None = None):
        self._cache = TTLCache(
            max_size=DEFAULT_CACHE_SIZE,
            default_ttl=cache_ttl if cache_ttl is not None else DEFAULT_CACHE_TTL,
        )
        self._proxy = proxy
```

3. `app/services/rank_service.py`：`RankService.__init__` 增加 `default_limit: int = 20` 参数并保存为 `self.default_limit`；`_warm_cache` 中 `cache_key = ("rank", 20, page)` → `cache_key = ("rank", self.default_limit, page)`。

- [ ] **Step 3: main.py 传递配置**

`app/main.py` 的 `ActressService(...)` 构造增加：

```python
        magnet_cache_ttl=config.magnet_cache_ttl,
        rank_limit_default=config.rank_limit_default,
```

- [ ] **Step 4: push.py batch delay 可配置**

`app/handlers/push.py` 中：

```python
            if batch_start + batch_size < len(user_ids):
                await asyncio.sleep(batch_size)
```

→

```python
            if batch_start + batch_size < len(user_ids):
                await asyncio.sleep(shared.config.push_batch_delay)
```

- [ ] **Step 5: conftest mock_config 补字段 + .env.example**

`tests/conftest.py` 的 `mock_config` 增加：

```python
    config.push_batch_delay = 0
    config.magnet_cache_ttl = 300
    config.rank_limit_default = 20
```

`.env.example` 增加：

```bash
# 推送批次间延迟（秒）
PUSH_BATCH_DELAY=5
# 磁力搜索缓存 TTL（秒）
MAGNET_CACHE_TTL=300
```

- [ ] **Step 6: 全量跑测试**

```bash
.venv/bin/python -m pytest tests/unit/ -q --no-header
```

Expected: 全部 PASS

- [ ] **Step 7: lint + commit**

```bash
ruff check app/
git add app/config.py app/main.py app/service.py app/services/rank_service.py app/magnet_search.py app/handlers/push.py tests/conftest.py .env.example
git commit -m "chore(config): make push batch delay and magnet cache TTL configurable"
```

---

### Task 9: E4 — 文档更新

**Files:**
- Modify: `README.md`（架构树、数据源、配置表）
- Modify: `CLAUDE.md`（架构树、模块清单）
- Modify: `.env.example`（PUSH_DIGEST_* 在 Task 10 补，此处不重复）

- [ ] **Step 1: README 架构树修正**

`README.md` 的 `app/` 架构树（约第 96-135 行）替换为当前实际结构：

```markdown
app/
├── main.py                  # 入口：构建 Application，注册 handler，启动轮询
├── config.py                # BotConfig 数据类，所有配置来自环境变量
├── service.py               # ActressService 门面，协调各子服务
├── health.py                # 健康检查：数据源状态、错误日志环形缓冲、报告生成
│
├── models/                  # Pydantic v2 模型（profile/works/actors/magnets/wiki/favorites）
├── formatters/              # HTML 消息构建（profile/magnets/favorites/rankings）
├── fav/                     # 收藏数据层（manager.py：MySQL CRUD + 推送去重）
│
├── services/
│   ├── wiki_service.py      # Wikipedia/Wikidata 资料（bio、社交链接）
│   ├── javbus_service.py    # JavBus 作品 & 磁力 (jvav 库)
│   ├── javdb_scraper.py     # JavDb 爬虫（curl_cffi + subprocess curl fallback）
│   ├── rank_service.py      # JavDb 排行榜 + 后台预热
│   ├── resolver.py          # ProfileResolver: 名称解析
│   ├── name_match_service.py# 模糊匹配、简繁转换 (OpenCC, pypinyin)
│   ├── i18n/                # 多语言 (zh_CN/en_US/ja_JP)
│   └── text_utils.py        # Unicode 规范化、CJK 检测
│
├── handlers/                # Telegram 更新处理器（common/search/magnet/favorites/
│                            #   rank/push/history/settings/stats/works/admin）
├── cache.py                 # TTLCache：线程安全 TTL 缓存 + JSON 持久化
├── magnet_search.py         # sukebei.nyaa.si 磁力搜索
├── secure_callback.py       # HMAC-SHA256 签名回调（含明文导航回调规范）
├── rate_limiter.py          # 令牌桶限流器
├── scheduler.py             # 定时任务（数据清理）
├── improved_utils.py        # 图片下载（requests + curl 子进程）
└── models.py                # （已拆分至 models/ 包）
```

同时删除 README 中 `fav_manager.py`、`i18n_service.py`、`http_utils.py` 的引用，`/admin` 加入命令参考表：

```markdown
| `/admin` | - | 健康检查（仅管理员） |
```

- [ ] **Step 2: CLAUDE.md 架构树修正**

`CLAUDE.md` 的 Architecture 代码块同步修正：
- `formatters/` 已是包（补 `admin.py` 到 handlers 列表）
- `fav/` 注释改为 `Favorites CRUD、推送去重（user_seen_works）、导出`
- 删除 `http_utils.py`、`fav_manager.py`、`i18n_service.py` 旧路径
- 补充：`user_seen_works` 表（按用户去重新作推送）、`user_push_settings.push_mode`（instant/digest/off）、`pushmode:` 明文回调、`/admin` 命令

- [ ] **Step 3: 检查无残留旧路径**

```bash
grep -rn "http_utils\|fav_manager\|i18n_service\.py\|BotSession" README.md CLAUDE.md docs/ 2>/dev/null || echo "clean"
```

Expected: `clean`（或仅剩历史 spec 文档中的合理引用）

- [ ] **Step 4: commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: sync architecture tree with current module layout"
```

---

## Phase 3: P3 新功能层

### Task 10: N1 — 推送汇总（digest）模式

**Files:**
- Modify: `app/fav/manager.py`（push_mode 列 + 迁移 + 方法）
- Modify: `app/handlers/push.py`（三态 UI、digest 队列、汇总发送 job）
- Modify: `app/config.py`、`app/main.py`（配置 + job 注册）
- Modify: `app/services/i18n/*.py`（digest 文案）
- Modify: `tests/conftest.py`（mock_config 补字段）
- Modify: `tests/unit/test_handlers_push.py`
- Create: `tests/unit/test_push_digest.py`

- [ ] **Step 1: 写失败测试（manager 层 push_mode）**

创建 `tests/unit/test_push_digest.py`：

```python
"""Digest push mode: settings, queue accumulation, digest message sending."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.fav import FavoritesManager
from app.models import MergedWork
from tests.unit.test_favorites import _mock_conn, _mock_pool_acquire


@pytest.fixture
def manager():
    pool = MagicMock()
    pool.acquire = _mock_pool_acquire(MagicMock())
    return FavoritesManager(pool)


@pytest.mark.asyncio
async def test_set_push_mode_digest(manager):
    manager._execute = AsyncMock(return_value=1)
    assert await manager.set_push_mode(123, "digest") is True
    sql = manager._execute.call_args[0][0]
    assert "push_mode" in sql


@pytest.mark.asyncio
async def test_set_push_mode_invalid(manager):
    manager._execute = AsyncMock(return_value=1)
    assert await manager.set_push_mode(123, "bogus") is False
    manager._execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_push_settings_returns_mode(manager):
    manager._select_one = AsyncMock(return_value={"push_enabled": 1, "push_mode": "digest", "last_check": None})
    settings = await manager.get_push_settings(123)
    assert settings["push_mode"] == "digest"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_push_digest.py -q --no-header
```

Expected: FAIL（`set_push_mode` 不存在）

- [ ] **Step 3: manager.py 实现 push_mode**

1. `_SQL_INIT` 中 `user_push_settings` 建表语句追加一列：

```python
        push_mode VARCHAR(10) NOT NULL DEFAULT 'instant',
```

（放在 `push_enabled` 之后）

2. `create()` 中 `_init_tables()` 之后调用 `await manager._ensure_push_mode_column()`，新增方法：

```python
    async def _ensure_push_mode_column(self) -> None:
        """幂等迁移：为旧库补充 push_mode 列，并回填历史开关状态。"""
        try:
            row = await self._select_one(
                """
                SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_push_settings'
                  AND COLUMN_NAME = 'push_mode'
                """
            )
            if row and row["cnt"]:
                return
            await self._execute(
                "ALTER TABLE user_push_settings "
                "ADD COLUMN push_mode VARCHAR(10) NOT NULL DEFAULT 'instant'"
            )
            await self._execute(
                "UPDATE user_push_settings SET push_mode = 'off' WHERE push_enabled = 0"
            )
            logger.info("user_push_settings.push_mode 列迁移完成")
        except Exception as e:
            logger.error(f"迁移 push_mode 列失败: {e}")
```

3. `get_push_settings` 返回 push_mode：

```python
            if row:
                return {
                    "push_enabled": row["push_enabled"],
                    "push_mode": row.get("push_mode", "instant"),
                    "last_check": str(row["last_check"]) if row.get("last_check") else None,
                }
            return {"push_enabled": 1, "push_mode": "instant", "last_check": None}
```

4. `set_push_enabled` 改为同时写 push_mode：

```python
    async def set_push_enabled(self, user_id: int, enabled: bool) -> bool:
        return await self.set_push_mode(user_id, "instant" if enabled else "off")

    async def set_push_mode(self, user_id: int, mode: str) -> bool:
        if mode not in ("instant", "digest", "off"):
            logger.warning(f"非法 push_mode: {mode}")
            return False
        try:
            await self._execute(
                """
                INSERT INTO user_push_settings (user_id, push_enabled, push_mode, last_check)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    push_mode = VALUES(push_mode),
                    push_enabled = VALUES(push_enabled)
                """,
                (user_id, 1 if mode != "off" else 0, mode),
            )
            return True
        except Exception as e:
            logger.error(f"设置推送模式失败: {e}")
            return False
```

5. `get_users_with_push_enabled` 的 SQL 改为：

```python
                SELECT DISTINCT f.user_id
                FROM favorites f
                LEFT JOIN user_push_settings ups ON f.user_id = ups.user_id
                WHERE ups.user_id IS NULL OR ups.push_mode <> 'off'
```

- [ ] **Step 4: 写失败测试（digest 不即时发送、入队）**

`tests/unit/test_push_digest.py` 追加：

```python
class TestDigestAccumulation:
    """check_and_push_new_works 对 digest 用户只入队不发送。"""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        import app.handlers.push as push_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_users_with_push_enabled.return_value = [12345]
        self._fav_mgr.get_push_settings.return_value = {
            "push_enabled": True, "push_mode": "digest", "last_check": None,
        }
        self._fav_mgr.get_favorites.return_value = {
            "items": [{"actress_name": "TestActress"}], "next_cursor": None, "total": 1,
        }
        self._fav_mgr.record_user_work.return_value = True
        self._fav_mgr.update_last_check = AsyncMock()
        monkeypatch.setattr(
            push_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr)
        )
        shared_global.service.query_profile_async.return_value = ActressProfile(
            found=True, query="TestActress", star_name="TestActress", star_id="T-1",
            latest_works=[MergedWork(id="DIGEST-001", img="", date="2026-08-15", title="Digest Work")],
        )
        shared_global.config.push_enabled_global = True
        shared_global.config.allowed_user_ids = {12345}
        shared_global.config.push_batch_delay = 0
        push_mod._digest_queue.clear()

    @pytest.mark.asyncio
    async def test_digest_user_queues_not_sends(self, shared_global, monkeypatch):
        from app.handlers.push import _digest_queue, check_and_push_new_works
        mocked_send = AsyncMock()
        monkeypatch.setattr(
            "app.handlers.push.send_new_work_notification", mocked_send
        )
        context = MagicMock()
        context.bot = AsyncMock()
        await check_and_push_new_works(context)
        mocked_send.assert_not_called()
        assert len(_digest_queue.get(12345, [])) == 1
        self._fav_mgr.record_user_work.assert_awaited_once()
```

- [ ] **Step 5: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_push_digest.py -q --no-header
```

Expected: FAIL（目前 digest 用户会走即时发送路径）

- [ ] **Step 6: push.py 实现三态 + digest 队列**

`app/handlers/push.py` 顶部追加：

```python
_PUSH_MODES = ("instant", "digest", "off")
_digest_queue: dict[int, list[dict]] = {}
```

`check_and_push_new_works` 的 `check_user` 内，获取收藏之前读取模式：

```python
            try:
                settings = await favorites_manager.get_push_settings(user_id)
                mode = settings.get("push_mode", "instant")
            except Exception:
                mode = "instant"
            if mode == "off":
                return []
```

`check_user` 的发送循环替换为：

```python
            if new_works_for_user:
                for item in new_works_for_user:
                    if mode == "digest":
                        _digest_queue.setdefault(user_id, []).append(item)
                    else:
                        try:
                            await send_new_work_notification(
                                context.bot, user_id, item["actress_name"], item["work"]
                            )
                        except Exception as e:
                            logger.error(f"推送作品给用户 {user_id} 失败: {e}")
```

文件末尾追加：

```python
async def check_and_send_digests(context: ContextTypes.DEFAULT_TYPE) -> None:
    """定时把 digest 队列合并成汇总消息发送给各用户。"""
    from . import _get_shared

    shared = _get_shared()
    if not shared.config.push_enabled_global:
        return
    if not getattr(shared.config, "push_digest_enabled", True):
        return
    if not _digest_queue:
        return
    logger.info("发送 digest 汇总: %d 个用户", len(_digest_queue))
    for user_id, items in list(_digest_queue.items()):
        try:
            await send_digest_message(context.bot, user_id, items)
            _digest_queue.pop(user_id, None)
        except Exception as e:
            logger.error(f"发送 digest 给用户 {user_id} 失败: {e}")


async def send_digest_message(bot: Bot, user_id: int, items: list[dict]) -> None:
    from . import _get_shared

    shared = _get_shared()
    lang = shared.service.i18n.DEFAULT_LANG
    try:
        fav_mgr = await get_favorites_manager()
        lang = await fav_mgr.get_user_language(user_id)
    except Exception:
        pass

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    by_actress: dict[str, list] = {}
    for item in items:
        by_actress.setdefault(item["actress_name"], []).append(item["work"])

    lines = [f"<b>{_('push_digest_title', len(items))}</b>", ""]
    keyboard_rows: list[list[InlineKeyboardButton]] = []
    for actress_name, works in by_actress.items():
        lines.append(f"<b>👩 {html.escape(actress_name)}</b>")
        for work in works[:3]:
            av_id = work.id or ""
            date = (work.date or "").strip()
            title = (work.title or "").strip()[:40]
            lines.append(
                f"🎬 <code>{html.escape(av_id)}</code>"
                + (f"  📅 {html.escape(date)}" if date else "")
                + (f"  📝 {html.escape(title)}" if title else "")
            )
            if av_id:
                keyboard_rows.append(
                    [
                        InlineKeyboardButton(
                            _("search_magnet_for", av_id),
                            callback_data=_short_callback("magnet", av_id),
                        )
                    ]
                )
        if len(works) > 3:
            lines.append(_("push_digest_more", len(works) - 3))
        lines.append("")

    img_url = ""
    for item in items:
        if item["work"].img:
            img_url = item["work"].img
            break

    keyboard = InlineKeyboardMarkup(keyboard_rows) if keyboard_rows else None
    await send_photo_with_fallback(
        bot=bot,
        chat_id=user_id,
        img_url=img_url,
        caption="\n".join(lines),
        proxy_addr=shared.config.proxy_addr,
        reply_markup=keyboard,
    )
```

- [ ] **Step 7: push_toggle_cmd 三态 + 回调**

`app/handlers/push.py` 的 `push_toggle_cmd` 整体替换为：

```python
@require_auth
async def push_toggle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    from .common import make_t

    _ = await make_t(shared, update)
    user = update.effective_user
    favorites_manager = await get_favorites_manager()

    if not context.args:
        settings = await favorites_manager.get_push_settings(user.id)
        mode = settings.get("push_mode", "instant")
        status_text = {
            "instant": _("push_status", _("push_mode_instant_btn")),
            "digest": _("push_status", _("push_mode_digest_btn")),
            "off": _("push_status", _("push_mode_off_btn")),
        }[mode]
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        _("push_mode_instant_btn"), callback_data="pushmode:instant"
                    )
                ],
                [
                    InlineKeyboardButton(
                        _("push_mode_digest_btn"), callback_data="pushmode:digest"
                    )
                ],
                [
                    InlineKeyboardButton(
                        _("push_mode_off_btn"), callback_data="pushmode:off"
                    )
                ],
            ]
        )
        await msg.reply_text(status_text, reply_markup=keyboard)
        return

    action = context.args[0].lower()
    if action in ("on", "enable", "开启"):
        await favorites_manager.set_push_mode(user.id, "instant")
        await msg.reply_text(_("push_enabled_msg"))
    elif action in ("digest", "汇总"):
        await favorites_manager.set_push_mode(user.id, "digest")
        await msg.reply_text(_("push_digest_enabled_msg"))
    elif action in ("off", "disable", "关闭"):
        await favorites_manager.set_push_mode(user.id, "off")
        await msg.reply_text(_("push_disabled_msg"))
    else:
        await msg.reply_text(_("push_usage"))


@require_auth_callback
async def push_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    from .common import make_t

    data = q.data or ""
    if not data.startswith("pushmode:"):
        await q.answer()
        return
    mode = data[len("pushmode:") :]
    if mode not in _PUSH_MODES:
        await q.answer()
        return

    _ = await make_t(shared, update)
    fav_mgr = await get_favorites_manager()
    await fav_mgr.set_push_mode(update.effective_user.id, mode)
    mode_label = _("push_mode_instant_btn" if mode == "instant"
                   else "push_mode_digest_btn" if mode == "digest"
                   else "push_mode_off_btn")
    await q.answer(_("push_mode_set", mode_label))
    await q.edit_message_text(_("push_mode_set", mode_label))
```

- [ ] **Step 8: i18n key（digest 文案）**

三个语言文件追加：

| key | zh_CN | en_US | ja_JP |
|-----|-------|-------|-------|
| `push_mode_instant_btn` | 逐条推送 | Instant push | 個別プッシュ |
| `push_mode_digest_btn` | 每日汇总 | Daily digest | 毎日まとめ |
| `push_mode_off_btn` | 关闭推送 | Turn off | オフ |
| `push_mode_set` | ✅ 推送模式已切换至 {} | ✅ Push mode set to {} | ✅ プッシュモードを {} に変更しました |
| `push_digest_enabled_msg` | ✅ 已开启每日汇总推送\n\n我们会把当天所有新作合并成一条消息发给你。 | ✅ Daily digest enabled.\n\nNew works will be merged into one daily message. | ✅ 毎日まとめを有効にしました。\n\n当日の新作を1つのメッセージにまとめてお知らせします。 |
| `push_digest_title` | 🎉 今日新作汇总（{} 部） | 🎉 Today's new works ({} items) | 🎉 今日の新作まとめ（{}件） |
| `push_digest_more` | ...还有 {} 部作品 | ...and {} more works | ...他{}作品 |

- [ ] **Step 9: config + main.py 注册**

`app/config.py`：`BotConfig` 增加 `push_digest_enabled: bool`、`push_digest_interval: int`；`from_env()`：

```python
            push_digest_enabled=_env_bool("PUSH_DIGEST_ENABLED"),
            push_digest_interval=_env_int("PUSH_DIGEST_INTERVAL", "86400"),
```

`app/main.py`：
1. import 追加 `push_mode_callback`；注册 `app.add_handler(CallbackQueryHandler(push_mode_callback, pattern=r"^pushmode:"))`
2. 推送 job 注册块追加：

```python
        if config.push_digest_enabled:
            job_queue.run_repeating(
                check_and_send_digests,
                interval=config.push_digest_interval,
                first=config.push_digest_interval,
            )
            logging.info(
                "已启用每日汇总推送，间隔: %s秒", config.push_digest_interval
            )
```

import 处追加 `check_and_send_digests`。

`.env.example` 追加：

```bash
# 每日汇总推送（digest）
PUSH_DIGEST_ENABLED=1
PUSH_DIGEST_INTERVAL=86400
```

- [ ] **Step 10: conftest + 既有测试适配**

`tests/conftest.py` 的 `mock_config` 追加：

```python
    config.push_digest_enabled = True
    config.push_digest_interval = 86400
```

`tests/unit/test_handlers_push.py`：
- `TestPushToggleCmd._setup`：`self._fav_mgr.get_push_settings.return_value = {"push_enabled": True, "push_mode": "instant", "last_check": None}`；新增 `self._fav_mgr.set_push_mode = AsyncMock()`，把断言 `set_push_enabled.assert_awaited_once()` 改为 `set_push_mode.assert_awaited_once_with(12345, "instant")` / `(12345, "off")`
- `TestCheckAndPushNewWorks._setup`：`get_push_settings` 返回 `{"push_enabled": True, "push_mode": "instant", "last_check": None}`；`update_last_check` mock 为 AsyncMock

- [ ] **Step 11: 写 digest 发送测试**

`tests/unit/test_push_digest.py` 追加：

```python
class TestSendDigestMessage:
    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        monkeypatch.setattr("app.improved_utils.download_image", lambda *a, **kw: None)

    @pytest.mark.asyncio
    async def test_sends_one_message_with_grouped_works(self):
        from app.handlers.push import send_digest_message
        bot = AsyncMock()
        items = [
            {"actress_name": "A", "work": MergedWork(id="A-001", img="", date="2026-08-15", title="T1")},
            {"actress_name": "A", "work": MergedWork(id="A-002", img="", date="2026-08-15", title="T2")},
            {"actress_name": "B", "work": MergedWork(id="B-001", img="", date="2026-08-15", title="T3")},
        ]
        await send_digest_message(bot, 12345, items)
        # img_url 为空 → send_photo_with_fallback 走 _send_text → bot.send_message
        bot.send_message.assert_awaited_once()
        text = bot.send_message.call_args.kwargs["text"]
        assert "A-001" in text
        assert "A-002" in text
        assert "B-001" in text
```

- [ ] **Step 12: 全量跑测试**

```bash
.venv/bin/python -m pytest tests/unit/ -q --no-header
```

Expected: 全部 PASS

- [ ] **Step 13: lint + commit**

```bash
ruff check app/
git add app/fav/manager.py app/handlers/push.py app/config.py app/main.py app/services/i18n/ tests/conftest.py tests/unit/test_handlers_push.py tests/unit/test_push_digest.py .env.example
git commit -m "feat(push): add digest mode (instant/digest/off) with daily summary"
```

---

### Task 11: N2 — 作品详情增强

**Files:**
- Modify: `app/models/works.py`（`JavBusWork.stars`）
- Modify: `app/services/javbus_service.py`（提取主演）
- Modify: `app/handlers/magnet.py`（详情卡 + 按钮 + 空结果引导）
- Modify: `app/services/i18n/*.py`（新 key）
- Create: `tests/unit/test_javbus_service.py`、`tests/unit/test_handlers_magnet.py`

- [ ] **Step 1: 写失败测试（模型 + 提取）**

创建 `tests/unit/test_javbus_service.py`：

```python
"""JavBusService: AV meta 提取主演字段。"""
from unittest.mock import MagicMock

import pytest

from app.models import JavBusWork
from app.services.javbus_service import JavBusService


def _make_service(av_dict):
    javbus = MagicMock()
    javbus.get_av_by_id.return_value = (200, av_dict)
    javbus.get_av_magnets.return_value = (200, [])
    return JavBusService(
        javbus_util=javbus,
        av_meta_cache=MagicMock(),  # get 返回 None
        javbus_limiter=MagicMock(),
        uncensored=False,
    )


def test_meta_extracts_stars_from_star_name():
    svc = _make_service({
        "date": "2026-08-01", "img": "https://javbus.com/a.jpg",
        "url": "https://javbus.com/x", "title": "T",
        "star_name": "三上悠亜",
    })
    work = svc.get_av_meta("SSIS-123")
    assert work.stars == ["三上悠亜"]


def test_meta_extracts_stars_list():
    svc = _make_service({
        "date": "", "img": "", "url": "", "title": "",
        "stars": ["A", "B"],
    })
    work = svc.get_av_meta("SSIS-123")
    assert work.stars == ["A", "B"]


def test_meta_no_stars():
    svc = _make_service({"date": "", "img": "", "url": "", "title": ""})
    work = svc.get_av_meta("SSIS-123")
    assert work.stars == []
```

- [ ] **Step 2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_javbus_service.py -q --no-header
```

Expected: FAIL（`JavBusWork` 无 `stars` 字段 → Pydantic 校验报错或属性缺失）

- [ ] **Step 3: 模型 + 提取实现**

1. `app/models/works.py` 的 `JavBusWork` 追加字段：

```python
class JavBusWork(BaseModel):
    id: str
    title: str = ""
    date: str = "未知"
    img: str = ""
    url: str = ""
    magnets: list[MagnetLink] = []
    stars: list[str] = []
```

2. `app/services/javbus_service.py` 的 `get_av_meta` 中，`result = JavBusWork(...)` 之前追加：

```python
                stars = self._extract_stars(av)
```

`result` 构造追加 `stars=stars`。新增方法：

```python
    @staticmethod
    def _extract_stars(av: dict[str, Any]) -> list[str]:
        """从 jvav 返回的 av dict 中提取主演名单（键名不固定，防御式提取）。"""
        stars: list[str] = []
        for key in ("star_name", "stars", "star"):
            value = av.get(key)
            if isinstance(value, str) and value.strip():
                stars.append(value.strip())
            elif isinstance(value, list):
                stars.extend(
                    str(v).strip() for v in value if str(v).strip() and str(v).strip() not in stars
                )
            if stars:
                break
        return stars
```

> 注：旧缓存无 `stars` 键时 `model_validate` 自动填默认空列表，无需缓存迁移（`av_meta_cache` 的 schema 版本号不动）。

- [ ] **Step 4: 跑测试确认通过**

```bash
.venv/bin/python -m pytest tests/unit/test_javbus_service.py -q --no-header
```

Expected: 全部 PASS

- [ ] **Step 5: 写失败测试（magnet 回复增强）**

创建 `tests/unit/test_handlers_magnet.py`：

```python
"""run_magnet_reply: 详情卡主演按钮 + 空结果引导。"""
from unittest.mock import AsyncMock

import pytest

from app.handlers.magnet import run_magnet_reply
from app.models import JavBusWork


@pytest.fixture(autouse=True)
def _setup(shared_global, monkeypatch):
    import app.handlers.magnet as magnet_mod
    import app.fav as fav_mod
    fav_mgr = AsyncMock()
    fav_mgr.increment_stat = AsyncMock()
    fav_mgr.record_favorite_query = AsyncMock()
    monkeypatch.setattr(magnet_mod, "get_favorites_manager", AsyncMock(return_value=fav_mgr))
    svc = shared_global.service
    svc.get_av_meta.return_value = JavBusWork(
        id="SSIS-123", title="T", date="2026-08-01",
        img="", url="https://javbus.com/x",
        stars=["三上悠亜"],
    )
    svc.get_av_magnets.return_value = []
    shared_global.config.magnet_timeout = 5
    shared_global.config.magnet_limit = 5


@pytest.mark.asyncio
async def test_detail_card_has_star_button(mock_msg):
    from app.secure_callback import short_callback
    await run_magnet_reply(mock_msg, "SSIS-123")
    texts = [c.args[0] for c in mock_msg.reply_text.call_args_list]
    assert any("三上悠亜" in t for t in texts)
```

- [ ] **Step 6: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_handlers_magnet.py -q --no-header
```

Expected: FAIL（详情卡当前无主演行）

- [ ] **Step 7: magnet.py 详情卡增强**

`app/handlers/magnet.py` 的 `run_magnet_reply` 详情卡块替换为：

```python
    # Send AV detail card if available
    if av_meta and av_meta.title:
        detail_lines = ["<b>🎬 作品详情</b>"]
        detail_lines.append(f"<b>番号：</b><code>{html.escape(av_meta.id)}</code>")
        detail_lines.append(f"<b>标题：</b>{html.escape(av_meta.title)}")
        if av_meta.date and av_meta.date != _("work_date_unknown"):
            detail_lines.append(f"<b>日期：</b>{html.escape(av_meta.date)}")
        detail_kb: list[list[InlineKeyboardButton]] = []
        if av_meta.stars:
            first_star = av_meta.stars[0]
            detail_lines.append(f"<b>{_('magnet_stars')}</b>{html.escape('、'.join(av_meta.stars[:5]))}")
            detail_kb.append(
                [
                    InlineKeyboardButton(
                        _("magnet_view_actress"),
                        callback_data=_short_callback("favquery", first_star),
                    )
                ]
            )
        with contextlib.suppress(Exception):
            await waiting.delete()
        try:
            await send_photo_with_fallback(
                msg,
                av_meta.img,
                "\n".join(detail_lines),
                shared.config.proxy_addr,
                reply_markup=InlineKeyboardMarkup(detail_kb) if detail_kb else None,
            )
        except Exception:
            logging.getLogger(__name__).warning("发送封面图片失败", exc_info=True)
```

import 追加：`from telegram import InlineKeyboardButton, InlineKeyboardMarkup`；`from ..secure_callback import short_callback as _short_callback`。

空结果引导——`run_magnet_reply` 末尾，`messages = format_magnet_messages(query, items, _t=_)` 之后：

```python
    if not items and av_meta and av_meta.url:
        # 空结果 + 有详情页 → 用带链接按钮的引导消息替换无按钮提示
        messages = [
            (
                _("magnet_no_result"),
                InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                _("magnet_open_javbus"),
                                url=av_meta.url,
                            )
                        ]
                    ]
                ),
            )
        ]
```

（`magnet_no_result` 已有 key，无需新增。）

- [ ] **Step 8: i18n key（详情卡）**

三个语言文件追加：

| key | zh_CN | en_US | ja_JP |
|-----|-------|-------|-------|
| `magnet_stars` | 👩 主演： | 👩 Stars: | 👩 出演： |
| `magnet_view_actress` | 👩 查看女优资料 | 👩 View actress profile | 👩 女優情報を見る |
| `magnet_open_javbus` | 🌐 在 JavBus 查看 | 🌐 View on JavBus | 🌐 JavBus で見る |

- [ ] **Step 9: 跑测试确认通过 + 全量**

```bash
.venv/bin/python -m pytest tests/unit/test_handlers_magnet.py tests/unit/test_javbus_service.py -q --no-header
.venv/bin/python -m pytest tests/unit/ -q --no-header
```

Expected: 全部 PASS

> 注：`run_magnet_reply` 现在用 `_` 需要定义 `lang` 与 `_`（函数内已有 `lang = shared.service.i18n.DEFAULT_LANG` 与 `def _(key, *a)`，位于详情卡块之前，实施时确认顺序）。

- [ ] **Step 10: lint + commit**

```bash
ruff check app/
git add app/models/works.py app/services/javbus_service.py app/handlers/magnet.py app/services/i18n/ tests/unit/test_javbus_service.py tests/unit/test_handlers_magnet.py
git commit -m "feat(magnet): work detail card with stars + actress button, empty-result JavBus link"
```

---

### Task 12: N3 — 管理员健康检查

**Files:**
- Create: `app/health.py`、`app/handlers/admin.py`、`tests/unit/test_health.py`、`tests/unit/test_handlers_admin.py`
- Modify: `app/cache.py`（hits/misses 计数 + stats()）
- Modify: `app/main.py`（START_TIME、ErrorRingHandler 注册、admin handler）
- Modify: `app/services/javdb_scraper.py`、`app/magnet_search.py`、`app/improved_utils.py`、`app/services/wiki_service.py`（打点）
- Modify: `app/services/i18n/*.py`、`tests/unit/test_cache.py`、`tests/conftest.py`

- [ ] **Step 1: 写失败测试（cache 计数）**

`tests/unit/test_cache.py` 追加：

```python
    def test_hits_and_misses_counted(self):
        cache = TTLCache(max_size=64, default_ttl=60)
        cache.set("a", 1)
        assert cache.get("a") == 1
        assert cache.get("missing") is None
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert 0 < stats["hit_rate"] < 1
```

- [ ] **Step 2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_cache.py::TestTTLCache::test_hits_and_misses_counted -q --no-header
```

（若测试类名不同，用 `-k hits` 运行）

Expected: FAIL（无 `stats` 方法 / 无 hits 属性）

- [ ] **Step 3: cache.py 实现计数**

`app/cache.py` 的 `__init__` 中追加：

```python
        self.hits = 0
        self.misses = 0
```

`get()` 中：命中分支（`self._data.move_to_end(key)` 后）加 `self.hits += 1`；未命中/过期分支加 `self.misses += 1`。文件末尾追加：

```python
    def stats(self) -> dict[str, int | float]:
        """Cache 统计：条目数、命中/未命中、命中率。"""
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._data),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 4) if total else 0.0,
            }
```

- [ ] **Step 4: 写失败测试（health 模块）**

创建 `tests/unit/test_health.py`：

```python
"""Health module: source status registry, error ring buffer, report building."""
import logging

from app.health import ErrorRingHandler, SourceStatus


def test_source_status_ok_and_fail():
    SourceStatus._status.clear()
    SourceStatus.ok("javdb")
    SourceStatus.fail("sukebei", "timeout")
    snap = SourceStatus.snapshot()
    by_name = {s["source"]: s for s in snap}
    assert by_name["javdb"]["error"] is None
    assert by_name["sukebei"]["error"] == "timeout"


def test_error_ring_handler_buffers():
    handler = ErrorRingHandler(maxlen=3)
    logger = logging.getLogger("test.health")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    for i in range(5):
        logger.error("boom %d", i)
    recent = handler.recent()
    assert len(recent) == 3
    assert "boom 2" in recent[0]
    logger.removeHandler(handler)
```

- [ ] **Step 5: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/unit/test_health.py -q --no-header
```

Expected: FAIL（`ModuleNotFoundError: No module named 'app.health'`）

- [ ] **Step 6: 创建 app/health.py**

```python
"""健康检查基础设施：数据源状态注册表、错误日志环形缓冲、报告生成。"""

from __future__ import annotations

import logging
import time
from collections import deque

from telegram.constants import ParseMode


class SourceStatus:
    """轻量数据源健康注册表（进程内）。"""

    _status: dict[str, tuple[float, str | None]] = {}

    @classmethod
    def ok(cls, source: str) -> None:
        cls._status[source] = (time.time(), None)

    @classmethod
    def fail(cls, source: str, error: str) -> None:
        cls._status[source] = (time.time(), error[:200])

    @classmethod
    def snapshot(cls) -> list[dict]:
        return [
            {"source": name, "ts": ts, "error": err}
            for name, (ts, err) in cls._status.items()
        ]


class ErrorRingHandler(logging.Handler):
    """保留最近 N 条 ERROR 日志的内存环形缓冲。"""

    def __init__(self, maxlen: int = 50) -> None:
        super().__init__(level=logging.ERROR)
        self._buf: deque[str] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        self._buf.append(
            f"{self.format(record)}"
        )

    def recent(self, n: int = 5) -> list[str]:
        return list(self._buf)[-n:]


_error_handler = ErrorRingHandler()
_error_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
)


def install_error_handler() -> ErrorRingHandler:
    logging.getLogger().addHandler(_error_handler)
    return _error_handler


def _fmt_uptime(start_ts: float) -> str:
    secs = int(time.time() - start_ts)
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    return f"{days}天 {hours}小时 {minutes}分"


async def collect_health(shared, fav_mgr) -> str:
    """构建健康检查报告文本。shared 为 handlers._SharedState。"""
    from .main import START_TIME

    def _(key, *a):
        return shared.service.i18n.t(key, "zh_CN", *a)

    lines = [f"<b>🩺 {_('admin_title')}</b>", ""]
    lines.append(f"⏱ {_('admin_uptime')}：{_fmt_uptime(START_TIME)}")

    # 缓存
    lines.append("")
    lines.append(f"<b>📦 {_('admin_cache_hdr')}</b>")
    caches = {
        "profile": shared.service.profile_cache,
        "av_meta": shared.service.av_meta_cache,
        "wiki": shared.service.wiki_page_cache,
        "rank": shared.service.rank_cache,
        "javdb": shared.service._javdb_cache,
    }
    for name, cache in caches.items():
        s = cache.stats()
        lines.append(
            f"{name}: {s['size']} 条 / 命中率 {s['hit_rate'] * 100:.0f}%"
        )

    # MySQL
    lines.append("")
    lines.append(f"<b>🗄 {_('admin_mysql_hdr')}</b>")
    try:
        pool = fav_mgr._pool
        lines.append(
            f"{_('admin_pool')}: {pool.size}/{pool.maxsize} | SELECT 1: {_('admin_ok')}"
        )
    except Exception:
        lines.append(f"SELECT 1: {_('admin_fail')}")

    # 数据源
    lines.append("")
    lines.append(f"<b>🌐 {_('admin_sources_hdr')}</b>")
    snap = SourceStatus.snapshot()
    if not snap:
        lines.append(_("admin_no_data"))
    for s in snap:
        status = _("admin_ok") if s["error"] is None else f"{_('admin_fail')} ({s['error']})"
        lines.append(f"{s['source']}: {status}")

    # 回调存储
    lines.append("")
    lines.append(f"<b>🔐 {_('admin_callbacks_hdr')}</b>")
    try:
        from .secure_callback import get_callback_store
        st = get_callback_store().get_stats()
        lines.append(f"{_('admin_callbacks_valid')}: {st['valid_entries']}")
    except Exception:
        lines.append(_("admin_fail"))

    # 最近错误
    lines.append("")
    lines.append(f"<b>⚠️ {_('admin_logs_hdr')}</b>")
    recent = _error_handler.recent(5)
    if not recent:
        lines.append(_("admin_no_errors"))
    for entry in recent:
        lines.append(f"<code>{entry[:300]}</code>")

    return "\n".join(lines)
```

- [ ] **Step 7: cache/打点接入**

1. `app/cache.py`（Step 3 已完成）
2. `app/services/javdb_scraper.py` 的 `_fetch` 末尾（return 前）：

```python
    result = _curl_get(url)
    if result is None:
        from ..health import SourceStatus
        SourceStatus.fail("javdb", "fetch failed")
    else:
        from ..health import SourceStatus
        SourceStatus.ok("javdb")
    return result
```

（把现有 `return _curl_get(url)` 拆开改写）

3. `app/magnet_search.py` 的 `_do_search`：`if resp.status_code != 200: return []` 前加 `SourceStatus.ok("sukebei")`；`except httpx.RequestError` 分支加 `SourceStatus.fail("sukebei", "request error")`；parse 失败分支加 fail
4. `app/improved_utils.py` 的 `download_image`：成功 return 前 `SourceStatus.ok("images")`；最终 `return None` 前 `SourceStatus.fail("images", "download failed")`（两处 max_retries 分支出口）。`download_image_via_curl` 同样处理（ok/fail("images")）
5. `app/services/wiki_service.py` 的 `wiki_page_by_lang`：`return result` 前 `SourceStatus.ok("wiki")`；`except` 分支 `SourceStatus.fail("wiki", str(e))`；`page 不存在` 分支 ok

- [ ] **Step 8: 创建 admin handler**

创建 `app/handlers/admin.py`：

```python
"""管理员命令：健康检查。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..fav import get_favorites_manager
from ..health import collect_health

if TYPE_CHECKING:
    from telegram import Update

logger = logging.getLogger(__name__)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import _get_shared

    shared = _get_shared()
    msg = update.effective_message
    if not msg:
        return
    user = update.effective_user
    if not user or user.id != shared.config.admin_user_id:
        await msg.reply_text(shared.service.i18n.t("admin_no_permission"))
        return

    try:
        fav_mgr = await get_favorites_manager()
        text = await collect_health(shared, fav_mgr)
        await msg.reply_text(
            text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
    except Exception as exc:
        logger.exception("admin health check failed: %s", exc)
        await msg.reply_text(shared.service.i18n.t("error_generic"))
```

- [ ] **Step 9: main.py 接入**

`app/main.py`：
1. 顶部追加 `import time` 与 `START_TIME = time.time()`
2. `main()` 中 `logging.basicConfig(...)` 之后追加：

```python
    from .health import install_error_handler

    install_error_handler()
```

3. import 追加 `from .handlers.admin import admin_cmd`；注册 `app.add_handler(CommandHandler("admin", admin_cmd))`

- [ ] **Step 10: i18n key（admin 文案）**

三个语言文件追加：

| key | zh_CN | en_US | ja_JP |
|-----|-------|-------|-------|
| `admin_no_permission` | 无权使用管理员命令。 | You are not allowed to use admin commands. | 管理者コマンドの使用権限がありません。 |
| `admin_title` | 机器人健康状态 | Bot Health Status | ボットの健全性 |
| `admin_uptime` | 运行时长 | Uptime | 稼働時間 |
| `admin_cache_hdr` | 缓存 | Caches | キャッシュ |
| `admin_mysql_hdr` | MySQL | MySQL | MySQL |
| `admin_pool` | 连接池 | Pool | 接続プール |
| `admin_sources_hdr` | 数据源 | Data Sources | データソース |
| `admin_callbacks_hdr` | 回调存储 | Callback Store | コールバックストア |
| `admin_callbacks_valid` | 有效条目 | Valid entries | 有効エントリ |
| `admin_logs_hdr` | 最近错误 | Recent Errors | 直近のエラー |
| `admin_ok` | ✅ | ✅ | ✅ |
| `admin_fail` | ❌ | ❌ | ❌ |
| `admin_no_data` | 暂无数据 | No data yet | データがありません |
| `admin_no_errors` | 无错误 | No errors | エラーなし |

- [ ] **Step 11: 写 admin handler 测试**

创建 `tests/unit/test_handlers_admin.py`：

```python
"""admin_cmd: 权限判断与报告输出。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.handlers.admin import admin_cmd


class TestAdminCmd:
    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        self._shared = shared_global
        shared_global.config.admin_user_id = 12345
        monkeypatch.setattr(
            "app.handlers.admin.get_favorites_manager",
            AsyncMock(return_value=AsyncMock()),
        )

    @pytest.mark.asyncio
    async def test_no_permission(self, mock_update, mock_context):
        mock_update.effective_user.id = 99999
        mock_update.effective_message = AsyncMock()
        await admin_cmd(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_report(self, mock_update, mock_context):
        mock_update.effective_user.id = 12345
        mock_update.effective_message = AsyncMock()
        with patch("app.handlers.admin.collect_health", new=AsyncMock(return_value="report")):
            await admin_cmd(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once_with(
            "report", parse_mode="HTML", disable_web_page_preview=True
        )
```

> 注：`mock_update` fixture 的 `effective_user.id = 12345` 默认值，`test_no_permission` 中覆盖为 99999 后需要恢复（fixture 每测试重建，无需手动恢复）。

- [ ] **Step 12: 全量跑测试**

```bash
.venv/bin/python -m pytest tests/unit/ -q --no-header
```

Expected: 全部 PASS

- [ ] **Step 13: lint + commit**

```bash
ruff check app/
git add app/health.py app/handlers/admin.py app/cache.py app/main.py app/services/javdb_scraper.py app/magnet_search.py app/improved_utils.py app/services/wiki_service.py app/services/i18n/ tests/unit/test_health.py tests/unit/test_handlers_admin.py tests/unit/test_cache.py
git commit -m "feat(admin): add /admin health check (caches, MySQL, sources, error ring)"
```

---

## Phase 4: 回归与手动验证

### Task 13: 全量回归 + 手动验证清单

**Files:** 无（验证任务）

- [ ] **Step 1: 全量单测 + lint + mypy**

```bash
.venv/bin/python -m pytest tests/unit/ -q --no-header
ruff check app/
.venv/bin/python -m mypy app/
```

Expected: 全部 PASS；ruff 0 errors；mypy 0 errors

- [ ] **Step 2: 手动验证清单（Docker 环境，逐项打勾）**

| # | 场景 | 期望 |
|---|------|------|
| 1 | 两个测试账号关注同一位女优，出现新作后跑一次推送检查 | 两个账号**都**收到推送（F1 修复生效） |
| 2 | Docker + HTTP_PROXY 下 `/search SSIS-123` | 磁力结果包含 sukebei.nyaa.si 来源（F2 修复生效） |
| 3 | `/s 三上悠亚` 后立即 `/history` | 出现该搜索记录；同一天重复搜同名字不重复记录（F3） |
| 4 | 直接发番号 `SSIS-123` 后 `/history` | 记录番号，历史按钮点击后走磁力搜索 |
| 5 | 女优资料页点"📰 最新作品"翻页 | 可翻到第 4+ 部作品（F4 修复生效） |
| 6 | 切英文/日文后走一遍：搜索、磁力、收藏、推送开关、历史、统计 | 无中文硬编码残留 |
| 7 | `/push` → 点"每日汇总" → 有收藏女优新作后等一个 digest 周期 | 收到一条合并汇总消息（N1） |
| 8 | `/search SSIS-123`（无磁力结果的番号） | 详情卡显示主演 + "查看女优资料"按钮；无结果时显示 JavBus 链接（N2） |
| 9 | 管理员账号 `/admin` | 显示运行时长、缓存命中率、MySQL 状态、数据源、最近错误（N3）；非管理员显示无权限 |
| 10 | 重启容器 | 服务正常启动，`push_mode` 列迁移幂等，无异常日志 |

- [ ] **Step 3: 若有问题，按 diagnose 流程修复后重跑 Step 1**

- [ ] **Step 4: 最终 commit（若手动验证有修正）**

```bash
git add -A
git commit -m "fix: address issues found during manual verification"
```

---

## 自审记录（planning 阶段已核对）

- **Spec 覆盖**：F1→Task 1、F2→Task 2、F3→Task 3、F4→Task 4、E1→Task 5、E2→Task 6、E3→Task 7、E5→Task 8、E4→Task 9、N1→Task 10、N2→Task 11、N3→Task 12、回归→Task 13。spec 全部条目均有对应任务。
- **类型一致性**：`record_user_work(user_id, actress_name, av_id)` 在 Task 1 定义、Task 10 复用；`set_push_mode(user_id, mode)` 在 Task 10 定义并被 push.py 与测试使用；`SourceStatus.ok/fail/snapshot`、`ErrorRingHandler.recent`、`cache.stats()` 在 Task 12 定义并被 health.py 使用，命名全文一致。
- **占位符检查**：无 TBD/TODO；所有代码步骤含完整代码。
