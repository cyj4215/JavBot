# JavBot 代码质量全面重构设计方案

> 日期：2026-07-12
> 状态：审核中

## 概述

对 JavBot 进行代码质量体系的全面现代化改造，涵盖类型系统、工具链、异步栈、文件结构、开发者体验五个维度。

---

## 1. Pydantic v2 类型系统

### 目标

消除 13 个文件、35 处 `Dict[str, Any]`，用 Pydantic v2 BaseModel 替代全部领域模型。

### 模型层级

```
app/models/
├── __init__.py      # re-export all
├── profile.py       # ActressProfile
├── works.py         # 作品模型 (JavBusWork, JavDbWork, MergedWork)
├── actors.py        # 演员模型 (ActorSearchResult, StarInfo)
├── magnets.py       # 磁力模型 (MagnetLink)
├── wiki.py          # Wiki 信息 (WikiExtra, SocialLink)
└── favorites.py     # 收藏模型 (FavoriteEntry)
```

### 关键设计决策

- `ActressProfile`: dataclass → Pydantic BaseModel
- `latest_works`: `Optional[List[Dict[str, Any]]]` → `Optional[list[MergedWork]]`
- `extra_info`: `Optional[Dict[str, Any]]` → `Optional[WikiExtra]`
- 序列化: 全程用 `.model_dump(mode='json')` / `.model_validate()`，确保递归 JSON 化
- `model_dump_json()` 替代 `json.dumps()`（TTLCache 序列化 + 回调存储）
- `WikiExtra.socials` 用 `list[SocialLink]`，不再退化回 `list[dict]`

### 受影响的文件

| 文件 | 变更 |
|------|------|
| `app/models.py` | 删除 / 改为 re-export |
| `app/service.py` | cache 存取用 `model_dump(mode='json')` / `model_validate` |
| `app/formatters.py` | 访问 `work.id` 替代 `work["id"]` |
| `app/services/javbus_service.py` | 返回 `WorkModel` |
| `app/services/javdb_scraper.py` | 返回 `WorkModel` / `ActorSearchResult` |
| `app/services/wiki_service.py` | 返回 `WikiExtra` |
| `app/services/rank_service.py` | 返回 `ActorSearchResult` |
| `app/magnet_search.py` | 返回 `MagnetLink` |
| `app/handlers/*.py` | 类型化访问 |
| `app/fav_manager.py` | 返回 `FavoriteEntry` |

---

## 2. 工具链现代化

### ruff 替代 flake8 + isort + black

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

# 第一阶段：先开安全的规则
[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP"]
ignore = ["E501"]

# 后续阶段逐步开启（见实施顺序）：
# "B"  — bugbear, 潜在的 bug 模式
# "SIM" — simplify, 化简建议
# "ARG" — unused arguments
# "RUF" — ruff 自定义规则
# "N"   — naming conventions（需确认）

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    # rev: 实施时验证最新版本（可能已到 v1.x，不硬编码猜测）
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
```

> pre-commit **不跑 pytest**，避免卡提交体验。测试由 CI 负责。

### CI 重写

- 移除 `continue-on-error: true`
- 移除失效的 `python test_favorites.py` / `test_simple.py`（文件已不存在）
- 新增 job: ruff check → mypy → pytest tests/unit/ → docker compose build

---

## 3. 异步栈统一 + curl_cffi

### httpx 替换 requests

新建 `app/session.py`:

```python
class BotSession:
    """全局 async HTTP session, 连接级 retry.
    
    使用方式（在 application 启动时创建，shutdown 时 close）：
        session = BotSession(proxy=...)
        ...
        await session.client.aclose()  # 避免 "Unclosed connector" 告警
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
```

> **注意 1：** httpx `AsyncHTTPTransport(retries=3)` 只重试 **连接错误**，不等价于原 `requests` 的 HTTP 状态码重试（429/5xx）。对 Wiki API 等可能返回 429 的模块，需在业务代码中加入手动重试。
>
> **注意 2：** Wiki 模块当前使用 `RateLimiter`（基于 `time.sleep()`），它在 `asyncio.to_thread` 下运行不阻塞事件循环。**若 Wiki 迁移到 httpx async 调用，`RateLimiter` 必须改为 async 实现**（`asyncio.Lock` + `asyncio.sleep`），否则 `time.sleep()` 会直接阻塞事件循环。建议保留 Wiki 在 `to_thread` 中运行，异步化推迟到后续优化。
>
> **注意 3：** `BotSession` 的生命周期应与 Application 绑定——在 `post_init` 中创建，在 Application shutdown 时 `await client.aclose()`。可考虑通过 `Application.bot_data` 传递。

替换路径:

| 模块 | 旧 | 新 |
|------|----|----|
| `wiki_service.py` | `requests.get` → `to_thread` | 保留 `to_thread` 模式（RateLimiter 兼容） |
| `magnet_search.py` | 全局 `requests.Session` 单例 | `BotSession` |
| `service.py` | `build_retry_session()` | 复用 `BotSession` |

### curl_cffi 替换 subprocess curl

```python
# javdb_scraper.py
from curl_cffi import requests as curl_requests

def _fetch(url: str) -> Optional[str]:
    resp = curl_requests.get(url, impersonate="chrome131", timeout=25)
    return resp.text
```

- 保留 `_curl_get()` 作为 fallback（curl_cffi 编译失败时），fallback 路径走 `await asyncio.to_thread(_curl_get, url)`
- 移除 `_CURL_HEADERS` 等硬编码 header（curl_cffi impersonate 自动处理）

### magnet_search 全局状态重构

当前 `magnet_search.py` 使用模块级全局变量（`_cache`, `_session`, `_session_lock`），设计不佳。趁 httpx 迁移一并重构为可实例化的类：

```python
class MagnetSearch:
    def __init__(self, proxy: str = ""):
        self._cache = TTLCache(...)
        self._client = BotSession(proxy).client
```

--- 

## 4. 大文件拆解

### fav_manager.py (592行) → fav/ 包

```
app/fav/
├── __init__.py          # re-export
├── manager.py           # CRUD (原 592 行中的约 350 行)
├── push.py              # 新作品推送检查 (约 100 行)
└── export.py            # 收藏导出功能 (约 50 行)
```

### handlers/favorites.py (459行) → 保留 handler，键盘构建移到 formatters

```
app/handlers/favorites.py        # 瘦身: 只留 handler
app/formatters/favorites.py      # ← 新: render_favorites_page 等
```

### i18n_service.py (533行) → 逻辑 + 数据分离

```
app/services/i18n/
├── __init__.py
├── service.py   # 查找 + fallback 逻辑
├── zh_CN.py     # 中文翻译数据
├── en_US.py     # 英文翻译数据
└── ja_JP.py     # 日文翻译数据
```

### wiki_service.py (345行) → 分包

```
app/services/wiki/
├── __init__.py
├── service.py    # Wikipedia 页面抓取
├── parser.py     # HTML/wiki 文本解析
└── wikidata.py   # Wikidata API 调用
```

### formatters.py (313行) → 分包

```
app/formatters/
├── __init__.py
├── profile.py     # format_profile
├── magnets.py     # format_magnet_messages
├── favorites.py   # render_favorites_page
└── rankings.py    # format_rankings, build_rank_keyboard
```

---

## 5. Makefile 自动化

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
```

---

## 6. 测试更新策略

Pydantic 迁移后，现有测试中 mock 返回 `Dict[str, Any]` 的桩代码需同步更新。

### 推荐方案：mock 返回 Pydantic model

```python
# 之前
mocker.patch("app.services.javdb_scraper.JavDbScraper.get_actors_ranking",
             return_value=[{"name": "三上悠亞", "url": "...", "avatar": ""}])

# 之后
from app.models.actors import ActorSearchResult
mocker.patch("app.services.javdb_scraper.JavDbScraper.get_actors_ranking",
             return_value=[ActorSearchResult(name="三上悠亞", url="...", avatar="")])
```

### 备选方案（低风险）：保持 dict，在 consumer 侧用 `model_validate`

```python
result = ActorSearchResult.model_validate(mock_dict)
```

推荐统一用方案一，理由：
- mypy 能检查 mock 返回类型
- 重构后 consumer 期望 model 而非 dict
- model 工厂比手拼 dict 更健壮（默认值、类型验证）

---

## 7. 缓存兼容性与迁移

### 问题

当前 `data/cache/*.json` 存储的是旧格式 dict。升级后：
- `latest_works` 从 `list[dict]` → `list[MergedWork]`（字段结构可能不同）
- `extra_info` 从 `dict` → `WikiExtra` serialized dict
- 旧缓存若字段名/类型不兼容，启动时会抛 `ValidationError`

### 方案

在 `ActressService.__init__()` 或缓存加载后执行一次性的格式检测与迁移：

```python
def _migrate_cache_if_needed(self):
    """升级后使旧缓存失效，避免 Pydantic validation error"""
    version_key = "cache_schema_version"
    version = self.profile_cache.get(version_key)
    if version != 2:
        self.profile_cache.clear()
        self.av_meta_cache.clear()
        self.wiki_page_cache.clear()
        self.profile_cache.set(version_key, 2, ttl=None)  # 永不过期
```

> 不迁移旧数据格式——直接使旧缓存失效，让系统重新填充。这样做成本最低（索引 > 缓存预热时间），且避免了逐字段兼容的复杂度。

---

## 8. 回滚策略

| 步骤 | 回滚方式 | 风险 |
|------|---------|------|
| ruff 迁移 | `git checkout` pyproject.toml + 回装 flake8/isort/black | 零，纯配置变更 |
| Pydantic 定义 | 删除 `app/models/` 目录 | 零，未生效 |
| 类型替换 | `git revert` 逐子步骤 | 中，每子步骤 mypy 通过 |
| 大文件拆解 | `git revert` 单个文件 move | 低，纯文件重组 |
| Makefile/pre-commit | 删除文件 | 零 |
| CI 重写 | `git checkout` .github/workflows/ | 低 |
| httpx/curl_cffi | `git revert` + 保留旧模块 | 中，需测试 fallback 路径 |

核心原则：**每个子步骤都是独立 revert 的 commit**。

---

## 9. 实施规划

### Phase A：核心代码质量（步骤 1-6）

| 步骤 | 内容 | 风险 | 验证方式 |
|------|------|------|----------|
| 1 | ruff 迁移 + pyproject.toml + 删除 flake8/isort/black/isort 配置 | 低 | `ruff check app/` + `ruff format --check app/` 通过 |
| 2 | Pydantic 模型定义（`app/models/`） | 低 | `import` 不报错 |
| 3a | wiki_service → WikiExtra 类型化 | 中 | mypy 通过，pytest tests/unit/test_* 通过 |
| 3b | javbus_service → WorkModel 类型化 | 中 | 同上 |
| 3c | javdb_scraper → WorkModel / ActorSearchResult 类型化 | 中 | 同上 |
| 3d | formatters 类型化 + 拆 `formatters/` 包 | 中 | 同上 |
| 3e | service + 各 handler 接入 typed model | 中 | 同上 |
| 4 | 剩余大文件拆解（fav/、i18n/） | 中 | pytest 通过 |
| 5 | Makefile + pre-commit | 低 | `make lint` 通过 |
| 5.5 | ruff 规则升级第二阶段：开启 `B, SIM, ARG, RUF`，逐项修复新增告警 | 低 | `ruff check app/` 零告警 |
| 6 | CI 重写 | 低 | PR 触发 CI 全绿 |
| 6.5 | **更新 CLAUDE.md** — flake8 命令 → ruff，文件路径更新，新增包结构说明 | 低 | 无 |

> **子步骤独立性说明：** 3a-3e 按数据源拆分，每个子步骤可独立 mypy + pytest 验证。3a 不依赖 3b，可并行。合并时保证「所有子步骤完成→mypy 全过」。

### Phase B：异步栈升级（步骤 7-8）

| 步骤 | 内容 | 风险 | 说明 |
|------|------|------|------|
| 7a | `BotSession` + `MagnetSearch` 类化 | 中 | 验证 magnet_search 正常 |
| 7b | curl_cffi → JavDbScraper，保留 fallback | 中高 | Docker Linux 下验证编译 |
| 8 | 移除废弃配置 + 全局 cleanup：删除 `build_retry_session`、`http_utils.py`、旧 `_curl_get`（如果不再 fallback） | 低 | 删除后 CI 通过 |

> Phase B **独立于** Phase A，Phase A 全部通过 CI 后才进入。若 curl_cffi 在 Docker 中编译失败，回退到 `subprocess curl` 方案。
