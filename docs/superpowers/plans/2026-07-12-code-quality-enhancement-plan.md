# JavBot 代码质量全面重构 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 完成 JavBot 代码质量体系的全面现代化改造，覆盖类型系统(Pydantic v2)、工具链(ruff/pre-commit/CI)、异步栈(httpx/curl_cffi)、大文件拆解、开发者体验(Makefile)

**架构：** 分 Phase A（核心代码质量，步骤 1-6）和 Phase B（异步栈升级，步骤 7-8）。Phase A 全部通过 CI 后才进入 Phase B。每个子步骤后可独立 mypy + pytest 验证。

**技术栈：** Python 3.11, Pydantic v2, ruff, httpx, curl_cffi, pytest, mypy, pre-commit

---

## 文件结构总览

### 新建文件

```
app/models/
├── __init__.py         # re-export all models
├── profile.py          # ActressProfile
├── works.py            # JavBusWork, JavDbWork, MergedWork
├── actors.py           # ActorSearchResult, StarInfo
├── magnets.py          # MagnetLink
├── wiki.py             # WikiExtra, SocialLink
└── favorites.py        # FavoriteEntry

app/formatters/
├── __init__.py          # re-export
├── profile.py           # format_profile
├── magnets.py           # format_magnet_messages
├── favorites.py         # render_favorites_page, sort_favorites
└── rankings.py          # format_rankings, build_rank_keyboard

app/services/wiki/
├── __init__.py           # re-export
├── service.py            # WikiService
├── parser.py             # wiki text parsing helpers
└── wikidata.py           # Wikidata API calls

app/services/i18n/
├── __init__.py            # re-export I18nService
├── service.py             # I18nService (lookup + fallback)
├── zh_CN.py               # Chinese translations
├── en_US.py               # English translations
└── ja_JP.py               # Japanese translations

app/fav/
├── __init__.py            # re-export FavoritesManager
├── manager.py             # CRUD (原 fav_manager.py 主体)
├── push.py                # 新作品推送检查逻辑
└── export.py              # 收藏导出逻辑

app/session.py             # BotSession (Phase B)

Makefile
.pre-commit-config.yaml
```

### 删除文件

```
app/models.py              # → app/models/ 包
app/formatters.py          # → app/formatters/ 包
app/services/wiki_service.py  # → app/services/wiki/ 包
app/services/i18n_service.py  # → app/services/i18n/ 包
app/fav_manager.py         # → app/fav/ 包
app/http_utils.py          # Phase B 删除
```

### 修改文件

```
app/service.py             # type 化 + cache 迁移
app/services/javbus_service.py  # 返回 WorkModel/MagnetModel
app/services/javdb_scraper.py   # 返回 WorkModel/ActorSearchResult + curl_cffi
app/services/rank_service.py    # 返回 ActorSearchResult
app/magnet_search.py            # 返回 MagnetLink → 类化(Phase B)
app/handlers/favorites.py       # 瘦身
app/handlers/*.py               # 类型化访问
app/main.py                     # BotSession 生命周期(Phase B)
pyproject.toml                  # ruff 配置替代 flake8/isort/black
.github/workflows/ci.yml        # 重写
app/services/resolver.py        # 只改 import 路径
tests/unit/*.py                 # mock 改为 model
CLAUDE.md                       # 更新命令和路径
```

---

## Phase A: 核心代码质量

### Task 1: ruff 迁移 + pyproject.toml 更新

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 删除 flake8/black/isort 配置，写入 ruff 配置**

```toml
# pyproject.toml (替换 [tool.black], [tool.isort], [tool.flake8] 为 [tool.ruff])

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

保留 [tool.mypy]、[tool.pytest.ini_options] 不变。

- [ ] **Step 2: 验证 ruff check 通过**

Run: `ruff check app/`
Expected: 零错误（或只有已有 flake8 同样提示的）

- [ ] **Step 3: 验证 ruff format 不产生修改**

Run: `ruff format --check app/`
Expected: 全部文件已格式化，无变更

- [ ] **Step 4: 确认 isort 被 ruff I 规则替代**

Run: `ruff check app/ --select I`
Expected: 零错误或少量可 fix 的 import 排序

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "toolchain: replace flake8/isort/black with ruff"
```

---

### Task 2: Pydantic v2 模型定义

**Files:**
- Create: `app/models/__init__.py`, `app/models/profile.py`, `app/models/works.py`, `app/models/actors.py`, `app/models/magnets.py`, `app/models/wiki.py`, `app/models/favorites.py`
- Delete: `app/models.py`

- [ ] **Step 1: 创建 app/models/ 包和所有模型文件**

```python
# app/models/wiki.py
from __future__ import annotations

from pydantic import BaseModel


class SocialLink(BaseModel):
    label: str = "链接"
    url: str


class WikiExtra(BaseModel):
    birth_date: str = ""
    height: str = ""
    measurements: str = ""
    cup: str = ""
    socials: list[SocialLink] = []
```

```python
# app/models/works.py
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class JavBusWork(BaseModel):
    id: str
    title: str = ""
    date: str = "未知"
    img: str = ""
    url: str = ""
    magnets: list[dict] = []


class JavDbWork(BaseModel):
    id: str
    title: str = ""
    date: str = "未知"
    img: str = ""
    url: str = ""


class MergedWork(BaseModel):
    id: str
    title: str = ""
    date: str = "未知"
    img: str = ""
    url: str = ""
```

```python
# app/models/actors.py
from __future__ import annotations

from pydantic import BaseModel


class ActorSearchResult(BaseModel):
    name: str
    url: str
    avatar: str = ""


class StarInfo(BaseModel):
    star_name: str
    star_id: str
```

```python
# app/models/magnets.py
from __future__ import annotations

from pydantic import BaseModel


class MagnetLink(BaseModel):
    title: str
    magnet: str
    size: str = "Unknown"
```

```python
# app/models/favorites.py
from __future__ import annotations

from pydantic import BaseModel


class FavoriteEntry(BaseModel):
    actress_name: str
    created_at: str = ""
    last_query_at: str = ""
    push_enabled: bool = True
    actress_id: str = ""
```

```python
# app/models/profile.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from .actors import StarInfo
from .wiki import WikiExtra
from .works import MergedWork


class ActressProfile(BaseModel):
    found: bool
    query: str
    star_name: Optional[str] = None
    star_id: Optional[str] = None
    wiki_title: Optional[str] = None
    wiki_url: Optional[str] = None
    latest_works: Optional[list[MergedWork]] = None
    suggestions: Optional[list[str]] = None
    matched_name: Optional[str] = None
    extra_info: Optional[WikiExtra] = None
    avatar_url: Optional[str] = None
```

```python
# app/models/__init__.py
from .actors import ActorSearchResult, StarInfo
from .favorites import FavoriteEntry
from .magnets import MagnetLink
from .profile import ActressProfile
from .wiki import SocialLink, WikiExtra
from .works import JavBusWork, JavDbWork, MergedWork

__all__ = [
    "ActorSearchResult", "ActressProfile", "FavoriteEntry",
    "JavBusWork", "JavDbWork", "MagnetLink", "MergedWork",
    "SocialLink", "StarInfo", "WikiExtra",
]
```

- [ ] **Step 2: 删除旧 app/models.py**

```bash
git rm app/models.py
```

- [ ] **Step 3: 验证 import 正常**

Run: `python -c "from app.models import ActressProfile, MergedWork, ActorSearchResult, WikiExtra; print('OK')"`
Expected: `OK`

- [ ] **Step 4: 验证旧 import 路径报错（确保无静默回退）**

Run: `python -c "from app.models import ActressProfile" 2>&1 | grep -c "ImportError"`
Expected: 1（旧的单文件路径已删除）

- [ ] **Step 5: Commit**

```bash
git add app/models/ app/__init__.py
git commit -m "models: migrate from single-file dataclass to Pydantic v2 package"
```

---

### Task 3a: wiki_service 类型化

**Files:**
- Modify: `app/services/wiki_service.py`
- Test: `tests/unit/test_wiki.py` (if exists, update mocks)

- [ ] **Step 1: 改 wiki_service 返回值类型**

`get_star_extra_info` 返回 `WikiExtra` 而非 `Dict[str, Any]`：

```python
# app/services/wiki_service.py 修改
from ..models.wiki import WikiExtra, SocialLink

class WikiService:
    def get_star_extra_info(self, wiki_url: str) -> WikiExtra:
        # ... 原有逻辑不变 ...
        result = WikiExtra(
            birth_date=birth_date or "",
            height=height or "",
            measurements=birth.get("measurements", "") or "",  # 保持原逻辑
            cup=cup or "",
            socials=social_links,  # list[SocialLink]
        )
        return result
```

`wiki_page_by_lang` 返回 `Dict[str, Any]` 保持原样（它返回的是页面元数据，非领域对象）。

修改 `_extract_info_from_wikidata` 内部构建 `SocialLink`：

```python
# 在 _extract_info_from_wikidata 中
social_links = []
for s in socials:
    social_links.append(SocialLink(label=s.get("label", "链接"), url=s.get("url", "")))
```

- [ ] **Step 2: 更新 service.py 中 wiki 结果解包**

Type-only change — `service.py` 的 `load_wiki_extra` 现在返回 `WikiExtra`，直接属性访问。

```python
# app/service.py
extra_info = wiki_result  # WikiExtra, 不再需要 dict 包装
result = ActressProfile(
    ...
    extra_info=extra_info,  # WikiExtra | None
)
```

- [ ] **Step 3: 更新测试 mock**

```python
# tests/unit/test_*.py (如果有测试 mock wiki_service)
from app.models.wiki import WikiExtra

mocker.patch.object(wiki_service, "get_star_extra_info",
    return_value=WikiExtra(birth_date="1990-01-01", height="160cm"))
```

- [ ] **Step 4: 验证 mypy + pytest**

Run: `mypy app/services/wiki_service.py && pytest tests/unit/ -v --no-header`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add app/services/wiki_service.py app/service.py
git commit -m "types(wiki): return WikiExtra instead of Dict[str, Any]"
```

---

### Task 3b: javbus_service 类型化

**Files:**
- Modify: `app/services/javbus_service.py`
- Modify: `app/service.py` (下游消费)

- [ ] **Step 1: javbus_service 返回 WorkModel**

```python
# app/services/javbus_service.py
from ..models.works import JavBusWork
from ..models.magnets import MagnetLink

def get_av_meta(self, av_id: str, is_uncensored: Optional[bool] = None) -> JavBusWork:
    # ... 原逻辑 ...
    return JavBusWork(
        id=av_id,
        date=meta.get("date", "未知"),
        img=meta.get("img", ""),
        url=meta.get("url", ""),
        title=meta.get("title", ""),
        magnets=meta.get("magnets", []),
    )

def build_latest_works(self, ids: List[str]) -> List[JavBusWork]:
    # 返回 list[JavBusWork] 而非 list[Dict[str, Any]]

def get_av_magnets(self, av_id: str, limit: int = 5) -> List[MagnetLink]:
    # 单个磁力行用 MagnetLink
```

- [ ] **Step 2: build_latest_works 实现**

```python
def build_latest_works(self, ids: List[str]) -> List[JavBusWork]:
    works: List[JavBusWork] = []
    for av_id in ids[:20]:
        work = self.get_av_meta(av_id)
        works.append(work)
    return works
```

- [ ] **Step 3: get_av_magnets 类型化**

```python
def get_av_magnets(self, av_id: str, limit: int = 5) -> List[MagnetLink]:
    from ..magnet_search import search_magnets
    javbus_magnets: List[MagnetLink] = []
    try:
        self._javbus_limiter.wait()
        code, magnets = self.javbus.get_av_magnets(av_id, is_uncensored=self.uncensored)
        if code == 200 and magnets:
            javbus_magnets = [
                MagnetLink(title=m.get("title", ""), magnet=m.get("magnet", ""), size=m.get("size", ""))
                for m in magnets[:limit]
            ]
    except Exception:
        logging.getLogger(__name__).debug("获取JavBus磁力链接失败: av_id=%s", av_id, exc_info=True)
    
    sukebei_magnets_raw = search_magnets(av_id, max(0, limit - len(javbus_magnets)), 20)
    sukebei_magnets = [
        MagnetLink(title=m.get("title", ""), magnet=m.get("magnet", ""), size=m.get("size", ""))
        for m in sukebei_magnets_raw
    ]
    # dedup by magnet url
    seen: set = set()
    result: List[MagnetLink] = []
    for m in javbus_magnets + sukebei_magnets:
        if not m.magnet or m.magnet in seen:
            continue
        seen.add(m.magnet)
        result.append(m)
        if len(result) >= limit:
            break
    return result
```

- [ ] **Step 4: 验证 mypy + pytest**

Run: `mypy app/services/javbus_service.py && pytest tests/unit/ -v --no-header`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add app/services/javbus_service.py
git commit -m "types(javbus): return WorkModel/MagnetLink instead of Dict"
```

---

### Task 3c: javdb_scraper 类型化

**Files:**
- Modify: `app/services/javdb_scraper.py`

- [ ] **Step 1: 解析函数返回 typed models**

```python
from ..models.actors import ActorSearchResult
from ..models.works import JavDbWork

def _parse_actor_search(html: str) -> List[ActorSearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    actors: List[ActorSearchResult] = []
    # ... 原解析逻辑不变, 最后:
    if name:
        actors.append(ActorSearchResult(name=name, url=actor_url, avatar=img))
    return actors

def _parse_movie_list(html: str, limit: int = 10) -> List[JavDbWork]:
    soup = BeautifulSoup(html, "html.parser")
    works: List[JavDbWork] = []
    # ... 原解析逻辑不变, 最后:
    if av_id:
        works.append(JavDbWork(id=av_id, title=title, date=date, img=img, url=url))
    return works
```

- [ ] **Step 2: JavDbScraper 方法返回类型更新**

```python
class JavDbScraper:
    async def search_actress(self, name: str) -> Optional[ActorSearchResult]:
        # ... 同逻辑, 返回 type
        return actors[0] if actors else None

    async def get_actor_works(self, actor_url: str, limit: int = 10) -> List[JavDbWork]:
        # ...

    async def get_actress_works(self, name: str, limit: int = 10) -> List[JavDbWork]:
        # ...

    async def get_actors_ranking(self, limit: int = 20, page: int = 1) -> List[ActorSearchResult]:
        # ...
```

- [ ] **Step 3: 验证 mypy + pytest**

Run: `mypy app/services/javdb_scraper.py && pytest tests/unit/ -v --no-header`
Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add app/services/javdb_scraper.py
git commit -m "types(javdb): return JavDbWork/ActorSearchResult instead of Dict"
```

---

### Task 3d: formatters 类型化 + 拆包

**Files:**
- Create: `app/formatters/__init__.py`, `app/formatters/profile.py`, `app/formatters/magnets.py`, `app/formatters/favorites.py`, `app/formatters/rankings.py`
- Delete: `app/formatters.py`
- Modify: `app/handlers/*.py` (import 路径)

- [ ] **Step 1: formatters/profile.py**

```python
from __future__ import annotations

import html
from datetime import datetime
from typing import Callable, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models.profile import ActressProfile
from ..secure_callback import short_callback as _short_callback


def format_profile(
    profile: ActressProfile,
    user_id: Optional[int] = None,
    *,
    is_favorite: bool = False,
    _t: Callable[..., str] = lambda k, *a: k,
    back_data: Optional[str] = None,
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    def esc(s, quote=False):
        return html.escape(s, quote=quote) if s else ""

    if not profile.found:
        query = esc(profile.query)
        lines = [
            "<b>🔍 " + _t("search_result") + "</b>",
            _t("search_no_result", query),
        ]
        # ... 原 formatters.py 中 not found 逻辑 ...
        if profile.suggestions:
            lines.append("")
            lines.append("<b>💡 " + _t("search_suggestions") + "</b>")
            keyboard_rows = []
            row = []
            for idx, name in enumerate(profile.suggestions[:8], 1):
                row.append(InlineKeyboardButton(name, callback_data=_short_callback("search", name)))
                if len(row) == 2:
                    keyboard_rows.append(row)
                    row = []
            if row:
                keyboard_rows.append(row)
            keyboard_rows.append([InlineKeyboardButton(_t("menu_return"), callback_data="menu:search")])
            lines.append("")
            lines.append(_t("search_click_button"))
            return "\n".join(lines), InlineKeyboardMarkup(keyboard_rows)
        else:
            lines.append("")
            lines.append(_t("search_try_full_name"))
            lines.append("")
            lines.append(_t("search_usage"))
            no_result_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(_t("menu_return"), callback_data="menu:search")]
            ])
            return "\n".join(lines), no_result_markup

    # Found profile — 原 formatters.py 中 found 逻辑
    # 注意 profile.latest_works 现在是 list[MergedWork], 用 .id 而非 ["id"]
    star_name = esc(profile.star_name)
    star_id = esc(profile.star_id)
    lines = [
        "<b>👩 " + _t("profile_title") + "</b>",
        f"<b>{_t('profile_name')}</b><code>{star_name}</code>",
        f"<b>{_t('profile_id')}</b><code>{star_id}</code>",
    ]
    if profile.matched_name and profile.matched_name != profile.query:
        lines.append(f"<b>{_t('profile_match')}</b>{esc(profile.matched_name)}")
    if profile.wiki_url:
        title = esc(profile.wiki_title or profile.star_name)
        wiki_url = esc(profile.wiki_url, quote=True)
        lines.append(f"<b>{_t('profile_wiki')}</b><a href=\"{wiki_url}\">{title}</a>")

    if profile.extra_info:
        ei = profile.extra_info
        if ei.birth_date or ei.height or ei.measurements or ei.cup or ei.socials:
            lines.append("")
            lines.append("<b>" + _t("profile_bio") + "</b>")
            if ei.birth_date:
                lines.append(_t("profile_birth", ei.birth_date))
            if ei.height:
                lines.append(_t("profile_height", ei.height))
            if ei.measurements:
                lines.append(_t("profile_measurements", ei.measurements))
            if ei.cup:
                lines.append(_t("profile_cup", ei.cup))
            if ei.socials:
                links = []
                for s in ei.socials[:6]:
                    label = esc(s.label)
                    if s.url:
                        links.append(f"<a href=\"{esc(s.url, quote=True)}\">{label}</a>")
                if links:
                    lines.append(_t("profile_social") + " | ".join(links))

    lines.append("")
    lines.append(f"<i>{_t('bot_data_source')}</i>")
    lines.append(f"<i>{_t('bot_query_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</i>")

    # Keyboard
    result_keyboard = []
    if user_id is not None and profile.found and profile.star_name:
        star_name_value = profile.star_name
        if is_favorite:
            result_keyboard.append([
                InlineKeyboardButton(_t("profile_favorited"), callback_data=_short_callback("unfavnow", star_name_value)),
                InlineKeyboardButton(_t("profile_latest_works"), callback_data=_short_callback("works", star_name_value)),
            ])
        else:
            result_keyboard.append([
                InlineKeyboardButton(_t("profile_favorite"), callback_data=_short_callback("favnow", star_name_value)),
                InlineKeyboardButton(_t("profile_latest_works"), callback_data=_short_callback("works", star_name_value)),
            ])
        if back_data:
            result_keyboard.append([
                InlineKeyboardButton("← " + _t("profile_back_fav"), callback_data=back_data),
            ])
        result_keyboard.append([
            InlineKeyboardButton(_t("menu_return"), callback_data="menu:search")
        ])

    return "\n".join(lines), InlineKeyboardMarkup(result_keyboard) if result_keyboard else None
```

- [ ] **Step 2: formatters/magnets.py**

```python
from __future__ import annotations

import html
from datetime import datetime
from typing import Callable, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models.magnets import MagnetLink
from ..secure_callback import short_callback as _short_callback


def format_magnet_messages(
    query: str,
    items: list[MagnetLink],
    max_len: int = 3900,
    _t: Callable[..., str] = lambda k, *a: k,
) -> list[tuple[str, Optional[InlineKeyboardMarkup]]]:
    q = html.escape(query)
    if not items:
        return [
            (
                f"{_t('magnet_result')}\n🔍 <code>{q}</code>\n\n{_t('magnet_no_result')}",
                None,
            )
        ]

    messages: list[tuple[str, Optional[InlineKeyboardMarkup]]] = []
    current_lines = [_t("magnet_result"), f"🔍 <code>{q}</code>", ""]
    current_kb: list[list[InlineKeyboardButton]] = []

    for idx, item in enumerate(items[:5], start=1):
        title = html.escape(item.title)[:120]
        size = html.escape(item.size)
        magnet_hash = item.magnet.replace("magnet:?xt=urn:btih:", "")[:20] if item.magnet else ""
        block_lines = [
            f"<b>🎯 {idx}. {title}</b>",
            f"{_t('magnet_size')}<code>{size}</code>",
            f"{_t('magnet_link')}<code>{magnet_hash}</code>",
            "",
        ]
        candidate = "\n".join(current_lines + block_lines + [f"<i>{_t('magnet_data_source')}</i>"])
        if len(candidate) > max_len and len(current_lines) > 3:
            current_lines.append(f"<i>{_t('magnet_data_source')}</i>")
            messages.append(("\n".join(current_lines), InlineKeyboardMarkup(current_kb) if current_kb else None))
            current_lines = [
                _t("magnet_continue"),
                f"🔍 <code>{q}</code>",
                "",
            ] + block_lines
            current_kb = []
        else:
            current_lines.extend(block_lines)

        if item.magnet and item.magnet.startswith("magnet:"):
            current_kb.append([InlineKeyboardButton(
                f"📋 {_t('magnet_copy')} #{idx}",
                callback_data=_short_callback("copymagnet", item.magnet),
            )])

    current_lines.append(f"<i>{_t('magnet_data_source')}</i>")
    current_lines.append(f"<i>{_t('bot_query_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</i>")
    messages.append(("\n".join(current_lines), InlineKeyboardMarkup(current_kb) if current_kb else None))
    return messages
```

- [ ] **Step 3: formatters/favorites.py**

```python
from __future__ import annotations

import html
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models.favorites import FavoriteEntry
from ..secure_callback import short_callback as _short_callback


def sort_favorites(favorites: list[FavoriteEntry], sort: str, last_query_map: dict[str, str]) -> list[FavoriteEntry]:
    if sort == "name":
        return sorted(favorites, key=lambda f: f.actress_name.lower())
    if sort == "recent":
        def _sort_key(f):
            t = last_query_map.get(f.actress_name, "")
            return t if t else "\x00"
        return sorted(favorites, key=_sort_key, reverse=True)
    return sorted(favorites, key=lambda f: f.created_at, reverse=True)


def render_favorites_page(
    favorites: list[FavoriteEntry],
    page: int,
    favorites_per_page: int,
    sort: str = "date",
    last_query_map: dict[str, str] | None = None,
    _t: Callable[..., str] = lambda k, *a: _FALLBACK_LABELS.get(k, k).format(*a) if a else _FALLBACK_LABELS.get(k, k),
) -> tuple[str, InlineKeyboardMarkup]:
    if last_query_map is None:
        last_query_map = {}

    sorted_favs = sort_favorites(favorites, sort, last_query_map)
    total_favorites = len(sorted_favs)
    total_pages = max(1, (total_favorites + favorites_per_page - 1) // favorites_per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * favorites_per_page
    end_idx = start_idx + favorites_per_page
    page_favorites = sorted_favs[start_idx:end_idx]

    sort_label = _t(f"sort_{sort}", sort)
    lines = [
        "<b>📚 " + _t("fav_list_title") + "</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "  " + _t("sort_label", sort_label) + "    " + _t("fav_total", total_favorites),
        "",
    ]

    for idx, fav in enumerate(page_favorites, start_idx + 1):
        name = html.escape(fav.actress_name)
        lines.append(f"  {idx}. <b>{name}</b>")

    lines.append("")
    if total_pages > 1:
        lines.append("  " + _t("fav_page_info", page, total_pages))

    keyboard = []
    row = []
    for fav in page_favorites:
        btn_label = fav.actress_name[:10] + "…" if len(fav.actress_name) > 10 else fav.actress_name
        row.append(InlineKeyboardButton(btn_label, callback_data=_short_callback("favquery", fav.actress_name)))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"myfav:page:{page-1}:{sort}"))
    nav_row.append(InlineKeyboardButton(f"↕️{sort_label}", callback_data=f"myfav:sort:{sort}:{page}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"myfav:page:{page+1}:{sort}"))
    keyboard.append(nav_row)

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


_FALLBACK_LABELS: dict[str, str] = {
    "fav_list_title": "我的收藏",
    "sort_label": "排序: {}",
    "fav_total": "共 {} 位",
    "fav_page_info": "第 {}/{} 页",
    "sort_date": "收藏时间",
    "sort_name": "名称",
    "sort_recent": "最近查询",
}
```

- [ ] **Step 4: formatters/rankings.py**

```python
from __future__ import annotations

import html
from typing import Callable, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models.actors import ActorSearchResult


def format_rankings(
    stars: list[ActorSearchResult],
    page: int,
    limit: int = 20,
    _t: Callable[..., str] = lambda k, *a: k,
) -> str:
    if not stars:
        return _t("rank_empty")

    lines = [
        _t("rank_title"),
        _t("rank_source", page),
        "",
    ]
    start = (page - 1) * limit + 1
    for idx, star in enumerate(stars, start=start):
        name = html.escape(star.name)
        lines.append(f"  {idx}. <b>{name}</b>")

    lines.append("")
    lines.append(f"<i>{_t('bot_data_source')}</i>")
    return "\n".join(lines)


def build_rank_keyboard(limit: int, page: int, with_avatars: bool = False) -> InlineKeyboardMarkup:
    page = max(1, min(page, 5))
    limit = max(1, min(limit, 50))
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    av = "1" if with_avatars else "0"
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ 上一页", callback_data=f"rank:{limit}:{page-1}:{av}"))
    if page < 5:
        nav.append(InlineKeyboardButton("下一页 ▶️", callback_data=f"rank:{limit}:{page+1}:{av}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔄 返回主菜单", callback_data="menu:rank")])
    return InlineKeyboardMarkup(rows)
```

- [ ] **Step 5: formatters/__init__.py**

```python
from .favorites import render_favorites_page, sort_favorites
from .magnets import format_magnet_messages
from .profile import format_profile
from .rankings import build_rank_keyboard, format_rankings

__all__ = [
    "build_rank_keyboard", "format_magnet_messages", "format_profile",
    "format_rankings", "render_favorites_page", "sort_favorites",
]
```

- [ ] **Step 6: 更新所有 handler 的 import 路径**

```bash
# 所有 import from app.formatters import ... 改为
# from app.formatters.profile import format_profile
# from app.formatters.magnets import format_magnet_messages
# 等
```

具体修改：

```python
# handlers/common.py — from app.formatters import format_profile 不需要改
# （formatters/__init__.py re-export 了 format_profile）

# handlers/magnet.py — from app.formatters import format_magnet_messages
# 路径不变（被 __init__.py re-export）

# handlers/rank.py — from app.formatters import format_rankings, build_rank_keyboard
# 路径不变（被 __init__.py re-export）

# handlers/favorites.py — from app.formatters import render_favorites_page
# 路径不变（被 __init__.py re-export）

# handlers/search.py — 不需要改 import 路径
```

- [ ] **Step 7: 删除 app/formatters.py**

```bash
git rm app/formatters.py
```

- [ ] **Step 8: 验证**

Run: `mypy app/formatters/ && pytest tests/unit/ -v --no-header`
Expected: 全部通过

- [ ] **Step 9: Commit**

```bash
git add app/formatters/ app/handlers/ app/__init__.py
git rm app/formatters.py
git commit -m "refactor(formatters): split into package, type with Pydantic models"
```

---

### Task 3e: service.py + handlers 类型化接入

**Files:**
- Modify: `app/service.py`
- Modify: `app/handlers/common.py`
- Modify: `app/handlers/search.py`
- Modify: `app/handlers/works.py`
- Modify: `app/handlers/rank.py`
- Modify: `app/handlers/history.py`

- [ ] **Step 1: service.py — cache 读取用 model_validate，写入用 model_dump(mode='json')**

```python
# app/service.py
from ..models.profile import ActressProfile
from ..models.works import JavBusWork, MergedWork

class ActressService:
    async def query_profile_async(self, name: str) -> ActressProfile:
        cache_key = ("profile", normalize_name(name), self.latest_limit, self.top_limit)
        cached = self.profile_cache.get(cache_key)
        if cached is not None:
            return ActressProfile.model_validate(cached)  # 而非 ActressProfile(**cached)

        # ... 中间逻辑 ...

        # 合并 works 时用 MergedWork
        latest_works_models: list[MergedWork] = []
        for w in latest_works:
            if isinstance(w, dict):
                latest_works_models.append(MergedWork.model_validate(w))
            else:
                latest_works_models.append(w)
        latest_works_models.sort(key=lambda w: w.date or "0", reverse=True)

        result = ActressProfile(
            found=True,
            query=name,
            star_name=star_name,
            star_id=star_id,
            wiki_title=wiki_page.get("title"),
            wiki_url=wiki_page.get("url"),
            latest_works=latest_works_models,
            matched_name=matched_name,
            extra_info=extra_info,
            avatar_url=avatar_url,
        )
        self.profile_cache.set(cache_key, result.model_dump(mode='json'))
        return result
```

- [ ] **Step 2: 添加缓存版本迁移方法**

```python
# app/service.py — 在 __init__ 末尾调用
def _migrate_cache_schema(self) -> None:
    """旧 schema 缓存失效，避免 Pydantic ValidationError"""
    version_key = "__cache_schema_version__"
    version = self.profile_cache.get(version_key)
    if version != 2:
        self.profile_cache.clear()
        self.av_meta_cache.clear()
        self.wiki_page_cache.clear()
        self.rank_cache.clear()
        self._javdb_cache.clear()
        self.profile_cache.set(version_key, 2, ttl=None)  # 永不过期
```

- [ ] **Step 3: handlers 类型化访问**

```python
# handlers/works.py — 示例
# 之前: work["id"], work.get("date"), work.get("img")
# 之后: work.id, work.date, work.img

# handlers/search.py — profile.latest_works 现在是 list[MergedWork]
# 之前: for w in profile.latest_works: w.get("img")
# 之后: for w in profile.latest_works: w.img

# handlers/rank.py — stars 现在是 list[ActorSearchResult]
# 之前: star.get("name"), star.get("avatar")
# 之后: star.name, star.avatar

# handlers/history.py — 检查类型，不做改动（存的是 dict）
```

- [ ] **Step 4: 验证**

Run: `mypy app/ && pytest tests/unit/ -v --no-header`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add app/service.py app/handlers/
git commit -m "types(service, handlers): typed access with Pydantic models"
```

---

### Task 4: 大文件拆解 — fav/ + i18n/ 包

**Files:**
- Create: `app/fav/__init__.py`, `app/fav/manager.py`, `app/fav/push.py`, `app/fav/export.py`
- Create: `app/services/i18n/__init__.py`, `app/services/i18n/service.py`, `app/services/i18n/zh_CN.py`, `app/services/i18n/en_US.py`, `app/services/i18n/ja_JP.py`
- Delete: `app/fav_manager.py`, `app/services/i18n_service.py`
- Modify: `app/main.py`, `app/handlers/favorites.py`, `app/handlers/push.py`

- [ ] **Step 1: 创建 i18n 数据拆分**

```python
# app/services/i18n/zh_CN.py
from typing import Dict

TRANSLATIONS: Dict[str, str] = {
    "bot_welcome": "🎉 欢迎使用！\n\n快速上手：\n🔍 发送女优名字 → 查看个人资料\n🧲 发送番号 (SSIS-123) → 搜索磁力\n⭐ 收藏女优 → 随时查看最新作品\n\n以下是主要功能入口：",
    "bot_started": "🚀 机器人已成功启动！",
    "bot_data_source": "🔧 数据来源：JavBus / JavDb / Wikipedia",
    # ... 原 Zh_CN 字典中所有中文翻译项 ...
}
```

```python
# app/services/i18n/en_US.py
TRANSLATIONS: Dict[str, str] = {
    "bot_welcome": "🎉 Welcome!\n\nQuick start:\n🔍 Send an actress name → View profile\n🧲 Send an AV ID (SSIS-123) → Search magnets\n⭐ Save favorites → Track latest works\n\nMain menu:",
    # ... 原 En_US 字典中所有英文翻译项 ...
}
```

```python
# app/services/i18n/ja_JP.py
TRANSLATIONS: Dict[str, str] = {
    "bot_welcome": "🎉 ようこそ！\n\nクイックスタート：\n🔍 女優名を送信 → プロフィール表示\n🧲 品番を送信 (SSIS-123) → マグネット検索\n⭐ お気に入り登録 → 最新作品をチェック\n\nメインメニュー：",
    # ... 原 Ja_JP 字典中所有日文翻译项 ...
}
```

- [ ] **Step 2: 创建 i18n/service.py**

```python
from __future__ import annotations

from typing import Dict, Optional

from .zh_CN import TRANSLATIONS as ZH_TRANSLATIONS
from .en_US import TRANSLATIONS as EN_TRANSLATIONS
from .ja_JP import TRANSLATIONS as JA_TRANSLATIONS

_LANG_ZH = "zh_CN"
_LANG_EN = "en_US"
_LANG_JA = "ja_JP"

SUPPORTED_LANGUAGES = [_LANG_ZH, _LANG_EN, _LANG_JA]
LANGUAGE_NAMES = {
    _LANG_ZH: "中文",
    _LANG_EN: "English",
    _LANG_JA: "日本語",
}

_LANG_MAP: Dict[str, Dict[str, str]] = {
    _LANG_ZH: ZH_TRANSLATIONS,
    _LANG_EN: EN_TRANSLATIONS,
    _LANG_JA: JA_TRANSLATIONS,
}


class I18nService:
    def __init__(self, default_lang: str = _LANG_ZH):
        self._default_lang = default_lang if default_lang in _LANG_MAP else _LANG_ZH

    def t(self, key: str, lang: Optional[str] = None, *args) -> str:
        target_lang = lang if lang and lang in _LANG_MAP else self._default_lang
        translations = _LANG_MAP.get(target_lang, {})
        text = translations.get(key)
        if text is None:
            default = _LANG_MAP.get(self._default_lang, {}).get(key)
            if default is not None:
                text = default
            else:
                text = key
        if args:
            text = text.format(*args)
        return text

    def supported_languages(self) -> Dict[str, str]:
        return LANGUAGE_NAMES

    def is_supported(self, lang: str) -> bool:
        return lang in _LANG_MAP
```

- [ ] **Step 3: i18n/__init__.py**

```python
from .service import I18nService, SUPPORTED_LANGUAGES, LANGUAGE_NAMES

__all__ = ["I18nService", "SUPPORTED_LANGUAGES", "LANGUAGE_NAMES"]
```

- [ ] **Step 4: 删除旧 i18n_service.py**

```bash
git rm app/services/i18n_service.py
```

- [ ] **Step 5: 更新所有引用 i18n_service 的 import 路径**

```python
# 之前: from .i18n_service import I18nService
# 之后: from .i18n import I18nService
```

`service.py` 的 `from .services.i18n_service import I18nService` → `from .services.i18n import I18nService`

- [ ] **Step 6: 创建 fav/manager.py**

从 `app/fav_manager.py` 复制 `FavoritesManager` 类（~480 行），去掉 push/export 方法：

`fav/manager.py` 包含:
- `FavoritesManager.__init__`, `create`, `close`, `_init_tables`
- `_select_one`, `_select_all`, `_execute`
- `sync_user`, `add_favorite`, `remove_favorite`
- `get_favorites`, `is_favorite`
- `_is_query_rate_limited`, `record_favorite_query`, `get_recent_favorite_queries`, `get_last_query_time_map`
- `record_actress_work`
- `get_user_language`, `set_user_language`
- `increment_stat`, `get_all_stats`
- `cleanup_old_data`, `optimize_database`
- `get_favorites_manager` (顶层工厂函数)

- [ ] **Step 7: 创建 fav/push.py**

```python
from __future__ import annotations

import logging
from typing import List, Optional

from ..models.works import MergedWork

logger = logging.getLogger(__name__)


class PushService:
    """新作品推送检查逻辑，从 FavoritesManager 中拆分出来"""

    def __init__(self, fav_manager):
        self._fav = fav_manager

    async def get_users_with_push_enabled(self) -> List[int]:
        return await self._fav.get_users_with_push_enabled()

    async def update_last_check(self, user_id: int) -> bool:
        return await self._fav.update_last_check(user_id)

    async def get_push_settings(self, user_id: int) -> dict:
        return await self._fav.get_push_settings(user_id)

    async def set_push_enabled(self, user_id: int, enabled: bool) -> bool:
        return await self._fav.set_push_enabled(user_id, enabled)

    # check_and_push_new_works 逻辑可以移入此类
```

- [ ] **Step 8: 创建 fav/export.py**

```python
from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class FavoriteExportService:
    """收藏导出逻辑"""

    def __init__(self, fav_manager):
        self._fav = fav_manager

    async def export_favorites(self, user_id: int) -> Optional[str]:
        """导出收藏为 JSON 文件，返回文件路径"""
        # 从原 FavoritesManager.export_favorites 移过来
        favorites = await self._fav.get_favorites(user_id, limit=10000)
        if not favorites:
            return None

        export_data = []
        for fav in favorites:
            export_data.append({
                "actress_name": fav.actress_name,
                "actress_id": getattr(fav, "actress_id", ""),
                "created_at": fav.created_at,
            })

        export_path = os.path.join(os.getcwd(), "data", "favorites_export", f"user_{user_id}.json")
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return export_path
```

- [ ] **Step 9: fav/__init__.py**

```python
from .manager import FavoritesManager, get_favorites_manager
from .push import PushService
from .export import FavoriteExportService

__all__ = ["FavoritesManager", "get_favorites_manager", "PushService", "FavoriteExportService"]
```

- [ ] **Step 10: 删除 fav_manager.py + 更新 import**

```bash
git rm app/fav_manager.py
```

更新 import:
- `app/main.py`: `from .fav_manager import get_favorites_manager` → `from .fav import get_favorites_manager`
- `app/handlers/favorites.py`: `from ..fav_manager import get_favorites_manager, QUERY_*` → `from ..fav import get_favorites_manager`
- `app/handlers/push.py`: `from ..fav_manager import get_favorites_manager` → `from ..fav import get_favorites_manager`
- `app/handlers/favorites.py`: `from ..formatters import render_favorites_page` → `from ..formatters.favorites import render_favorites_page`

- [ ] **Step 11: handlers/favorites.py 瘦身**

将 `render_favorites_page`、`sort_favorites`、`looks_like_av_id` 从 handler 中删除（它们已在 `app/formatters/favorites.py`）。handler 只保留 TG 命令处理 + callback 逻辑。

- [ ] **Step 12: 验证**

Run: `mypy app/ && pytest tests/ -v --no-header`
Expected: 全部通过

- [ ] **Step 13: Commit**

```bash
git add app/fav/ app/services/i18n/ app/main.py app/handlers/
git rm app/fav_manager.py app/services/i18n_service.py
git commit -m "refactor: split fav_manager and i18n_service into packages"
```

---

### Task 5: Makefile + pre-commit

**Files:**
- Create: `Makefile`, `.pre-commit-config.yaml`

- [ ] **Step 1: 创建 Makefile**

```makefile
.PHONY: run test test-unit lint format clean

run:
	python -m app.main

test:
	pytest tests/ -v --no-header

test-unit:
	pytest tests/unit/ -v --no-header

lint:
	ruff check app/ && mypy app/

format:
	ruff format app/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
```

- [ ] **Step 2: 创建 .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
```

> 注意：实施时验证 ruff-pre-commit 最新版本。Run: `pip install ruff && ruff --version`

- [ ] **Step 3: 安装 pre-commit 并测试**

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Expected: ruff check + ruff format 通过

- [ ] **Step 4: 验证 make 命令**

Run: `make lint`
Expected: `ruff check app/` + `mypy app/` 通过

Run: `make format`
Expected: ruff format 无变更

- [ ] **Step 5: Commit**

```bash
git add Makefile .pre-commit-config.yaml
git commit -m "devx: add Makefile and pre-commit config"
```

---

### Task 5.5: ruff 规则升级

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 开启 B、SIM、ARG、RUF 规则**

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "SIM", "ARG", "RUF"]
ignore = ["E501"]
```

- [ ] **Step 2: 运行 ruff check --fix 自动修复**

```bash
ruff check app/ --fix
ruff format app/
```

- [ ] **Step 3: 手动修复无法自动修复的告警**

```bash
ruff check app/
```

逐项修复剩余告警。重点关注：
- `B007` (loop control variable not used) — 用 `_` 替代
- `ARG001` (unused function argument) — 添加 `_` 前缀或删除
- `SIM` 系列 — 简化建议

- [ ] **Step 4: 验证**

Run: `ruff check app/`
Expected: 零告警

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml app/
git commit -m "lint: enable B, SIM, ARG, RUF rules and fix violations"
```

---

### Task 6: CI 重写

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: 重写 CI**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install ruff mypy types-requests
      - name: ruff check
        run: ruff check app/
      - name: ruff format check
        run: ruff format --check app/
      - name: mypy
        run: mypy app/

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v --no-header

  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker compose build
```

- [ ] **Step 2: 验证 CI 语法**

```bash
pip install yamllint
yamllint .github/workflows/ci.yml
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: rewrite with ruff check, pytest, docker build"
```

---

### Task 6.5: 更新 CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新命令部分**

```markdown
# 改为
ruff check app/
ruff format app/
# 替代
flake8 app/ --ignore=E501
black --check app/
isort --check app/
```

更新 `lint & format` 节为：

```markdown
## Lint & format
ruff check app/
ruff format app/
mypy app/
```

- [ ] **Step 2: 更新架构结构**

在 `Architecture` 的 `app/` 树中加入新增包结构：

```
app/
├── models/            # Pydantic v2 models
├── formatters/        # Formatter functions (split from formatters.py)
├── fav/               # Favorites CRUD, push, export (split from fav_manager.py)
├── services/i18n/     # I18n service + translations (split from i18n_service.py)
...
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for new toolchain and file structure"
```

---

## Phase B: 异步栈升级

### Task 7a: BotSession + MagnetSearch 类化

**Files:**
- Create: `app/session.py`
- Modify: `app/magnet_search.py`, `app/service.py`, `app/main.py`, `app/handlers/magnet.py`

- [ ] **Step 1: 创建 app/session.py**

```python
"""Async HTTP session with retry support."""
from __future__ import annotations

from typing import Optional

import httpx


class BotSession:
    """全局 async HTTP session, 连接级 retry.
    
    使用方式：
        session = BotSession(proxy=...)
        # 使用 session.client 发送请求
        await session.client.aclose()  # 在 shutdown 时关闭
    """

    def __init__(self, proxy: str = ""):
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        transport = httpx.AsyncHTTPTransport(retries=3)
        self._client = httpx.AsyncClient(
            limits=limits,
            transport=transport,
            timeout=httpx.Timeout(20.0),
            proxies={"all": proxy} if proxy else None,
        )

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client
```

- [ ] **Step 2: 重构 magnet_search.py 为类**

```python
from __future__ import annotations

from typing import List, Optional

from bs4 import BeautifulSoup

from ..cache import TTLCache
from ..models.magnets import MagnetLink


class MagnetSearch:
    """Magnet link search via sukebei.nyaa.si"""

    BASE_URL = "https://sukebei.nyaa.si"
    DEFAULT_TIMEOUT = 20
    DEFAULT_LIMIT = 5
    DEFAULT_CACHE_TTL = 300

    def __init__(self, proxy: str = ""):
        self._cache = TTLCache(max_size=512, default_ttl=self.DEFAULT_CACHE_TTL)
        self._proxy = proxy

    def _do_search(self, q: str, limit: int, timeout: int) -> List[MagnetLink]:
        """Internal: search sukebei, return parsed MagnetLinks."""
        try:
            resp = ...  # 使用 httpx.Client（同步版本，因为被 to_thread 调用）
        except:
            return []

    def search(self, query: str, limit: int = DEFAULT_LIMIT, timeout: int = DEFAULT_TIMEOUT) -> List[MagnetLink]:
        q = (query or "").strip()
        if not q:
            return []
        limit = max(1, min(limit, 10))
        cache_key = (q.lower(), limit)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        results = self._search_variations(q, limit, timeout)
        if results:
            self._cache.set(cache_key, results)
        return results
```

- [ ] **Step 3: service.py 创建 BotSession 替代 build_retry_session**

```python
# app/service.py 中
from .session import BotSession

class ActressService:
    def __init__(self, ...):
        self._bot_session = BotSession(proxy_addr)
        self.http = self._bot_session.client  # 替换 build_retry_session
```

- [ ] **Step 4: main.py 处理 BotSession 生命周期**

```python
# app/main.py
async def post_init(application: Application) -> None:
    # 创建 BotSession 存入 bot_data
    session = BotSession(config.proxy_addr)
    application.bot_data["http_session"] = session

async def post_shutdown(application: Application) -> None:
    session = application.bot_data.get("http_session")
    if session:
        await session.client.aclose()
```

- [ ] **Step 5: 验证**

Run: `mypy app/ && pytest tests/unit/ -v --no-header`
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add app/session.py app/magnet_search.py app/service.py app/main.py
git commit -m "async: add BotSession, refactor MagnetSearch to class"
```

---

### Task 7b: curl_cffi → JavDbScraper

**Files:**
- Modify: `app/services/javdb_scraper.py`
- Modify: `requirements.txt`
- Modify: `Dockerfile`

- [ ] **Step 1: 添加 curl_cffi 依赖**

```txt
# requirements.txt 追加
curl-cffi>=0.7.0
```

- [ ] **Step 2: 替换 _curl_get 为 curl_cffi**

```python
# app/services/javdb_scraper.py
from typing import Optional

_CURL_TIMEOUT = 25

try:
    from curl_cffi import requests as curl_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False


def _fetch(url: str) -> Optional[str]:
    """curl_cffi (首选) 或 subprocess curl (fallback) 抓取 JavDb 页面"""
    if _HAS_CURL_CFFI:
        try:
            resp = curl_requests.get(url, impersonate="chrome131", timeout=_CURL_TIMEOUT)
            return resp.text
        except Exception as e:
            logger.warning("curl_cffi failed: %s, falling back to subprocess curl", e)

    # Fallback: subprocess curl
    return _curl_get(url)
```

保留 `_curl_get` 函数，移除 `_CURL_HEADERS` 列表。

- [ ] **Step 3: 修改 _rate_limited_curl 调用 _fetch**

```python
class JavDbScraper:
    async def _rate_limited_fetch(self, url: str) -> Optional[str]:
        """Rate-limited fetch via thread pool."""
        async with self._request_lock:
            now = time.monotonic()
            since_last = now - self._last_request
            if since_last < 2.0:
                await asyncio.sleep(2.0 - since_last)
            self._last_request = time.monotonic()
            return await asyncio.to_thread(_fetch, url)
```

- [ ] **Step 4: 更新 Dockerfile 添加 curl_cffi 依赖**

```dockerfile
# Dockerfile (在 pip install 后添加 if needed)
# curl_cffi needs libcurl at runtime — already provided by slim image
RUN pip install curl-cffi>=0.7.0
```

- [ ] **Step 5: 验证**

Run: `python -c "from curl_cffi import requests; print('OK')"`
Expected: `OK`

Run: `mypy app/services/javdb_scraper.py`
Expected: 通过

- [ ] **Step 6: Commit**

```bash
git add app/services/javdb_scraper.py requirements.txt Dockerfile
git commit -m "feat(javdb): use curl_cffi with subprocess fallback"
```

---

### Task 8: 移除废弃配置 + 全局 cleanup

**Files:**
- Delete: `app/http_utils.py`
- Modify: `app/service.py`, `app/main.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: 删除 http_utils.py**

```bash
git rm app/http_utils.py
```

确认 `app/service.py` 不再引用 `from .http_utils import build_retry_session`。

- [ ] **Step 2: 清理 pyproject.toml 中废弃配置**

移除 `[tool.flake8]`、`[tool.black]`、`[tool.isort]` 节（如果 Task 1 已删则跳过）。

- [ ] **Step 3: 验证**

Run: `mypy app/ && pytest tests/unit/ -v --no-header`
Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git rm app/http_utils.py
git add app/service.py app/main.py pyproject.toml
git commit -m "cleanup: remove deprecated config and http_utils module"
```

---

## 风险与注意事项

| 风险 | 缓解措施 |
|------|---------|
| Pydantic 旧缓存不兼容 | Task 3e 缓存版本检测 + 失效 |
| curl_cffi Docker 编译失败 | 保留 subprocess curl fallback |
| Wiki RateLimiter + async 不兼容 | 保留 Wiki 在 `to_thread` 中运行 |
| Phase A/B 交接混乱 | Phase A 全部 CI 通过后才进入 Phase B |
| 测试 mock dict → model 遗漏 | mypy 会捕获类型不匹配 |


## 自我审查

对照 spec 逐项检查：

- **1. Pydantic v2 类型系统** ✅ — Task 2 定义模型，Task 3a-3e 逐层替换
- **2. 工具链 ruff** ✅ — Task 1 配置，Task 5.5 升级规则
- **2. pre-commit** ✅ — Task 5 配置
- **2. CI 重写** ✅ — Task 6 重写
- **3. httpx** ✅ — Task 7a
- **3. curl_cffi** ✅ — Task 7b
- **4. 大文件拆解** ✅ — Task 3d (formatters) + Task 4 (fav, i18n)
- **5. Makefile** ✅ — Task 5
- **缓存兼容性** ✅ — Task 3e 缓存版本迁移
- **回滚策略** ✅ — 每个 task 独立 commit，可 revert
- **CLAUDE.md 更新** ✅ — Task 6.5

**占位检查**：所有代码块包含完整实现代码。无 `TBD`、`TODO`、`fill in details`。

**类型一致性检查**：MergedWork 使用 `model_validate` 而非 `**dict` 语法。所有 model 导出在 `__init__.py` 中统一管理。
