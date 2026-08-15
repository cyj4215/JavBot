# 逐条推送消息格式美化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 将逐条推送（instant push）消息改为「标题置顶式」排版：番号加粗置顶、标题引用块、胶囊标签、新增「查看详情」URL 按钮，并把排版逻辑抽到独立纯函数 formatter。

**Architecture:** 新增 `app/formatters/push.py` 纯函数 `format_push_notification(actress_name, work, _t) -> (caption, keyboard)`（仿 `favorites.py` 模式，i18n 经 `_t` 注入），`handlers/push.py` 的 `send_new_work_notification` 瘦身为「查语言 → 调 formatter → 发送」。i18n 三语言同步增删键。

**Tech Stack:** Python 3.11, python-telegram-bot 21.6（支持 `<blockquote>`）, pytest + pytest-asyncio, ruff, mypy（strict）。

**Spec:** `docs/superpowers/specs/2026-08-16-push-format-design.md`

---

### Task 1: 更新 i18n 三语言推送键

**Files:**
- Modify: `app/services/i18n/zh_CN.py:81-86`
- Modify: `app/services/i18n/en_US.py:81-86`
- Modify: `app/services/i18n/ja_JP.py:81-86`
- Test: `tests/unit/test_i18n.py`（已有，验证三语言键齐全）

**Note:** 只**新增**键（`push_actress_tag`/`push_date_tag`/`push_detail_btn`）并**改写** `push_title`，**保留** `push_actress`/`push_av_id`/`push_date`/`push_title_label` 四个旧键——`app/handlers/push.py:182-188` 仍引用它们，删除推迟到 Task 4 与 handler 重写同提交。

- [x] **Step 1: 修改 zh_CN.py**

把（约 81-86 行）：

```python
    "push_title": "🎉 关注女优更新啦！",
    "push_actress": "👩 女优：",
    "push_av_id": "🎬 番号：",
    "push_date": "📅 日期：",
    "push_title_label": "📝 标题：",
    "push_unknown": "未知",
```

替换为（新增 `push_actress_tag`/`push_date_tag`/`push_detail_btn`、改写 `push_title`；**保留**四个旧键）：

```python
    "push_title": "🔔 关注的女优有新作品",
    "push_actress": "👩 女优：",
    "push_av_id": "🎬 番号：",
    "push_date": "📅 日期：",
    "push_title_label": "📝 标题：",
    "push_actress_tag": "👩 {}",
    "push_date_tag": "📅 {}",
    "push_detail_btn": "🔗 查看详情",
    "push_unknown": "未知",
```

- [x] **Step 2: 修改 en_US.py**

把（约 81-86 行）：

```python
    "push_title": "🎉 Your favorite actress has a new work!",
    "push_actress": "👩 Actress:",
    "push_av_id": "🎬 AV ID:",
    "push_date": "📅 Date:",
    "push_title_label": "📝 Title:",
    "push_unknown": "Unknown",
```

替换为（新增 `push_actress_tag`/`push_date_tag`/`push_detail_btn`、改写 `push_title`；**保留**四个旧键）：

```python
    "push_title": "🔔 Your favorite actress has a new work!",
    "push_actress": "👩 Actress:",
    "push_av_id": "🎬 AV ID:",
    "push_date": "📅 Date:",
    "push_title_label": "📝 Title:",
    "push_actress_tag": "👩 {}",
    "push_date_tag": "📅 {}",
    "push_detail_btn": "🔗 Details",
    "push_unknown": "Unknown",
```

- [x] **Step 3: 修改 ja_JP.py**

把（约 81-86 行）：

```python
    "push_title": "🎉 お気に入りの新作が出ました！",
    "push_actress": "👩 女優：",
    "push_av_id": "🎬 品番：",
    "push_date": "📅 日付：",
    "push_title_label": "📝 タイトル：",
    "push_unknown": "不明",
```

替换为（新增 `push_actress_tag`/`push_date_tag`/`push_detail_btn`、改写 `push_title`；**保留**四个旧键）：

```python
    "push_title": "🔔 お気に入りの新作が出ました！",
    "push_actress": "👩 女優：",
    "push_av_id": "🎬 品番：",
    "push_date": "📅 日付：",
    "push_title_label": "📝 タイトル：",
    "push_actress_tag": "👩 {}",
    "push_date_tag": "📅 {}",
    "push_detail_btn": "🔗 詳細",
    "push_unknown": "不明",
```

- [x] **Step 4: 运行 i18n 测试验证三语言键齐全**

Run: `pytest tests/unit/test_i18n.py tests/unit/test_i18n_coverage.py -v --no-header`
Expected: 全部 PASS（键增删后三语言仍然一致、无空值；handler 引用的键仍全部存在）

- [x] **Step 5: Commit**

```bash
git add app/services/i18n/zh_CN.py app/services/i18n/en_US.py app/services/i18n/ja_JP.py
git commit -m "feat(i18n): new push notification keys (context line, tags, detail button)"
```

---

### Task 2: 编写 `format_push_notification` 失败测试

**Files:**
- Test: `tests/unit/test_formatters.py`（文件末尾追加 `TestFormatPushNotification` 类）

- [x] **Step 1: 追加测试类**

在 `tests/unit/test_formatters.py` 末尾追加（顶部已 import `InlineKeyboardButton, InlineKeyboardMarkup`；补 import `from app.formatters.push import format_push_notification` 和 `from app.models import MergedWork`——MergedWork 已由 `app.models` 导出）：

```python
class TestFormatPushNotification:
    """format_push_notification: caption layout, tags, buttons, escaping."""

    _LABELS = {
        "push_title": "NEW",
        "push_unknown": "?",
        "push_actress_tag": "👩 {}",
        "push_date_tag": "📅 {}",
        "push_detail_btn": "DETAIL",
        "search_magnet_for": "MAG {}",
        "push_query_btn": "Q {}",
    }

    def _t(self, key, *a):
        val = self._LABELS.get(key, key)
        return val.format(*a) if a else val

    def test_full_work(self):
        work = MergedWork(
            id="TEST-001", title="Test Title", date="2026-07-01",
            img="", url="https://example.com/work/TEST-001",
        )
        caption, keyboard = format_push_notification("TestActress", work, _t=self._t)
        assert caption.startswith("NEW")
        assert "<b>🎬 <code>TEST-001</code></b>" in caption
        assert "<blockquote>Test Title</blockquote>" in caption
        assert "<code>👩 TestActress</code>" in caption
        assert "<code>📅 2026-07-01</code>" in caption
        row = keyboard.inline_keyboard[0]
        assert len(row) == 3
        detail = next(b for b in row if b.text == "DETAIL")
        assert detail.url == "https://example.com/work/TEST-001"

    def test_missing_title_and_date(self):
        work = MergedWork(id="TEST-002")
        caption, keyboard = format_push_notification("TestActress", work, _t=self._t)
        assert "<blockquote>" not in caption
        assert "📅" not in caption
        assert len(keyboard.inline_keyboard[0]) == 2

    def test_unknown_date_sentinel_omitted(self):
        work = MergedWork(id="TEST-003", date="未知")
        caption, _ = format_push_notification("TestActress", work, _t=self._t)
        assert "📅" not in caption

    def test_no_url_means_no_detail_button(self):
        work = MergedWork(id="TEST-004", url="")
        _, keyboard = format_push_notification("TestActress", work, _t=self._t)
        row = keyboard.inline_keyboard[0]
        assert len(row) == 2
        assert all(b.url is None for b in row)

    def test_html_escaping(self):
        work = MergedWork(
            id="TEST-005", title="<script>alert(1)</script>", date="2026-01-01",
        )
        caption, _ = format_push_notification("A&B", work, _t=self._t)
        assert "<script>" not in caption
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in caption
        assert "A&amp;B" in caption

    def test_missing_id_uses_push_unknown(self):
        work = MergedWork(id="")
        caption, _ = format_push_notification("TestActress", work, _t=self._t)
        assert "<code>?</code>" in caption

    def test_long_title_truncated_to_200(self):
        work = MergedWork(id="TEST-006", title="X" * 500)
        caption, _ = format_push_notification("TestActress", work, _t=self._t)
        assert "<blockquote>" + "X" * 200 + "</blockquote>" in caption
```

- [x] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_formatters.py::TestFormatPushNotification -v --no-header`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.formatters.push'`

---

### Task 3: 实现 `app/formatters/push.py` 并通过测试

**Files:**
- Create: `app/formatters/push.py`
- Modify: `app/formatters/__init__.py:1-14`

- [x] **Step 1: 创建 formatter**

`app/formatters/push.py` 完整内容：

```python
from __future__ import annotations

import html
from collections.abc import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models import MergedWork
from ..secure_callback import short_callback as _short_callback

_TITLE_MAX = 200
_UNKNOWN_DATE = "未知"  # MergedWork.date 模型的哨兵默认值


def format_push_notification(
    actress_name: str,
    work: MergedWork,
    _t: Callable[..., str] = lambda k, *a: k,
) -> tuple[str, InlineKeyboardMarkup]:
    """构建逐条推送的 caption 与键盘，返回 (caption, keyboard)。"""
    av_id = work.id or _t("push_unknown")
    title_raw = (work.title or "").strip()[:_TITLE_MAX]
    date = (work.date or "").strip()

    lines = [
        _t("push_title"),
        f"<b>🎬 <code>{html.escape(av_id)}</code></b>",
    ]
    if title_raw:
        lines.append(f"<blockquote>{html.escape(title_raw)}</blockquote>")

    tags = [html.escape(_t("push_actress_tag", actress_name))]
    if date and date != _UNKNOWN_DATE:
        tags.append(html.escape(_t("push_date_tag", date)))
    lines.append("　".join(f"<code>{tag}</code>" for tag in tags))

    row = [
        InlineKeyboardButton(
            _t("search_magnet_for", av_id),
            callback_data=_short_callback("magnet", av_id),
        ),
        InlineKeyboardButton(
            _t("push_query_btn", actress_name),
            callback_data=_short_callback("favquery", actress_name),
        ),
    ]
    if work.url:
        row.append(InlineKeyboardButton(_t("push_detail_btn"), url=work.url))

    return "
".join(lines), InlineKeyboardMarkup([row])
```

- [x] **Step 2: 在 `app/formatters/__init__.py` 导出**

把：

```python
from .favorites import looks_like_av_id, render_favorites_page, sort_favorites
```

改为：

```python
from .favorites import looks_like_av_id, render_favorites_page, sort_favorites
from .push import format_push_notification
```

并把 `__all__` 加入 `"format_push_notification"`（字母序：在 `format_profile` 之前）。

- [x] **Step 3: 运行测试确认通过**

Run: `pytest tests/unit/test_formatters.py -v --no-header`
Expected: `TestFormatPushNotification` 全部 PASS，其余既有 formatter 测试不受影响

- [x] **Step 4: Commit**

```bash
git add app/formatters/push.py app/formatters/__init__.py tests/unit/test_formatters.py
git commit -m "feat(push): extract format_push_notification formatter (B2 layout, T2 tags)"
```

---

### Task 4: 重构 `send_new_work_notification` 使用 formatter

**Files:**
- Modify: `app/handlers/push.py:1-25`（import 区）和 `:157-216`（函数体）
- Modify: `app/services/i18n/zh_CN.py` / `app/services/i18n/en_US.py` / `app/services/i18n/ja_JP.py`（删除已不使用的四个旧键）
- Test: `tests/unit/test_handlers_push.py:152-175`（应保持通过，不改）

- [x] **Step 1: 删除三语言中已不使用的四个旧键**

`send_new_work_notification` 切换为 formatter（Step 3）后，handler 不再引用 `push_actress`/`push_av_id`/`push_date`/`push_title_label`。在三个语言文件中删除这四行（位于 `push_title` 与 `push_actress_tag` 之间）：

```python
    "push_actress": "👩 女优：",
    "push_av_id": "🎬 番号：",
    "push_date": "📅 日期：",
    "push_title_label": "📝 标题：",
```

（en_US 对应 `"👩 Actress:"` / `"🎬 AV ID:"` / `"📅 Date:"` / `"📝 Title:"`；ja_JP 对应 `"👩 女優："` / `"🎬 品番："` / `"📅 日付："` / `"📝 タイトル："`）

> 旧键必须与 handler 引用移除（Step 3）在**同一提交**中删除，避免出现引用缺失键的中间状态。提交前运行 `pytest tests/unit/test_i18n.py tests/unit/test_i18n_coverage.py -v --no-header` 确认绿色。

- [x] **Step 2: 添加 import**

在 `app/handlers/push.py` 的 import 区（现有 `from ..models import MergedWork` 之后）加：

```python
from ..formatters.push import format_push_notification
```

- [x] **Step 3: 替换函数体**

把 `send_new_work_notification` 中从 `try:`（当前 173 行）到函数结尾的整段（包含手拼 lines、keyboard、send_photo_with_fallback 调用）替换为：

```python
    try:
        caption, keyboard = format_push_notification(actress_name, work, _t=_)
        await send_photo_with_fallback(
            bot=bot,
            chat_id=user_id,
            img_url=work.img or "",
            caption=caption,
            proxy_addr=shared.config.proxy_addr,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"发送新作品通知失败: {e}")
```

同时删除函数中不再使用的 `av_id`、`av_date`、`av_title`、`img` 变量和 `lines`、`keyboard` 的旧构建代码。若 `html` import 在文件其他地方已无使用，一并移除（`grep -n 'html.' app/handlers/push.py` 确认）。

- [x] **Step 4: 运行 handler 测试**

Run: `pytest tests/unit/test_handlers_push.py -v --no-header`
Expected: 全部 PASS（现有断言只查 `bot.send_message` 被调用——无图时 `send_photo_with_fallback` 走 `_send_text` 路径）

- [x] **Step 5: 运行相关测试全量确认**

Run: `pytest tests/unit/test_formatters.py tests/unit/test_handlers_push.py tests/unit/test_push_digest.py tests/unit/test_i18n.py tests/unit/test_i18n_coverage.py -v --no-header`
Expected: 全部 PASS

- [x] **Step 6: Commit**（连同 Step 1 删除的旧键一起提交）

```bash
git add app/handlers/push.py app/services/i18n/zh_CN.py app/services/i18n/en_US.py app/services/i18n/ja_JP.py
git commit -m "refactor(push): use format_push_notification in send_new_work_notification"
```

---

### Task 5: 全量验证（lint / type / 单元测试）

**Files:** 无新增改动，验证用

- [x] **Step 1: ruff 检查与格式化**

Run: `ruff check app/ && ruff format --check app/`
Expected: 无错误；若有 format drift，运行 `ruff format app/` 后重新检查

- [x] **Step 2: mypy 严格检查**

Run: `mypy app/`
Expected: 无错误（formatter 参数/返回均有标注，`_t` 为 `Callable[..., str]` 与既有 formatter 一致）

- [x] **Step 3: 全量单元测试**

Run: `pytest tests/unit/ -v --no-header`
Expected: 全部 PASS（既有测试不受影响）

- [x] **Step 4: Commit（如有 lint 修复）**

```bash
git add -A
git commit -m "chore: lint fixes after push format refactor" || echo "nothing to commit"
```

---

## Self-Review 记录

- **Spec 覆盖**：B2 布局（Task 3 格式）、T2 胶囊标签（`<code>` 包裹）、查看详情按钮（`work.url` 非空才加，Task 3）、i18n 键新增与 `push_title` 改写（Task 1，旧键保留至 Task 4）、旧键移除（Task 4，与 handler 引用切换同提交）、7 项边界（Task 2 测试逐一覆盖）、handler 瘦身（Task 4）、测试与验证（Task 2/5）。全部落实。
- **占位符扫描**：无 TBD/TODO；每个代码步骤含完整代码。
- **类型一致性**：`format_push_notification` 签名在 Task 2（测试）与 Task 3（实现）中一致；按钮文本键名（`push_actress_tag`/`push_date_tag`/`push_detail_btn`）与 Task 1 i18n 新增键一致；`push_unknown` 语义（缺失番号显示）与旧行为一致。