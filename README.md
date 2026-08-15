# Telegram JAV 女优信息查询机器人

一个功能丰富的 Telegram Bot，发送女优姓名或番号即可查询个人资料、作品列表、磁力链接，支持收藏管理、排行榜、新作推送和多语言。

## 功能一览

| 功能 | 说明 |
|------|------|
| **🔍 女优搜索** | 按日文名/中文名/英文名/罗马音搜索，支持简繁转换、模糊匹配、别名联想 |
| **📋 个人资料** | 头像、出生日期、身高、三围、罩杯、社交链接（来自 Wikipedia/Wikidata） |
| **🎬 作品查询** | 最新作品（含封面）、高分作品排行，数据源 JavBus + JavDb |
| **🧲 磁力搜索** | `/search` `/magnet` `/m` 或直接发番号，数据源 sukebei.nyaa.si |
| **🏆 热门排行** | `/rank` 查看 JavDb 实时排行榜，分页浏览，支持缓存 |
| **⭐ 收藏管理** | `/fav` 收藏 / `/unfav` 取消 / `/myfav` 列表 / `/exportfav` 导出 |
| **📢 新作推送** | `/push` 订阅收藏女优的新作品推送（定时检查） |
| **📜 搜索历史** | `/history` 最近搜索记录，支持一键重新搜索 |
| **📊 使用统计** | `/stats` 查看机器人使用数据 |
| **🌐 多语言** | `/language` 切换界面语言: 中文 / English / 日本語 |
| **🔒 安全回调** | 按钮回调数据 HMAC-SHA256 签名，防止篡改 |

## 截图预览

<details>
<summary>展开查看</summary>

运行后添加机器人，发送女优姓名或番号即可。所有交互均通过 Telegram 内联键盘完成。

</details>

## 快速开始

### 1. 准备 Telegram Bot Token

在 Telegram [@BotFather](https://t.me/BotFather) 创建机器人并获取 Token。

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填写：

```bash
TELEGRAM_BOT_TOKEN=你的token
MYSQL_ROOT_PASSWORD=设置一个密码
```

### 3. Docker 运行（推荐）

```bash
docker compose up -d --build
```

自动启动 MySQL 8.0 + 机器人容器，首次启动会自动建库建表。

### 4. 使用

发送女优姓名给机器人：

- 三上悠亜
- 明日花キララ
- Yua Mikami

或使用命令：

```
/s 三上悠亚
/search SSIS-123
/rank 20 1
```

直接发送 `SSIS-123` 这样的番号也会自动触发磁力搜索。

## 命令参考

| 命令 | 参数 | 说明 |
|------|------|------|
| `/start` | - | 启动，显示主菜单 |
| `/help` | - | 帮助信息 |
| `/s` | `<名称>` | 搜索女优资料 |
| `/search` `/magnet` `/m` | `<番号/关键词>` | 搜索磁力链接 |
| `/rank` | `[数量] [页码]` | 热门女优排行榜 |
| `/fav` | `<女优名>` | 收藏女优 |
| `/unfav` | `<女优名>` | 取消收藏 |
| `/myfav` | - | 查看收藏列表 |
| `/favlatest` | - | 收藏女优的最新作品 |
| `/exportfav` | - | 导出收藏列表为文件 |
| `/push` | - | 订阅/退订新作推送 |
| `/history` | - | 最近搜索历史 |
| `/stats` | - | 使用统计 |
| `/language` | - | 切换界面语言 |
| `/admin` | - | 健康检查（仅管理员） |

## 架构

```
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

### 数据源

| 数据源 | 用途 | 访问方式 |
|--------|------|----------|
| **JavBus** | 女优搜索、作品元数据、磁力 | `jvav` 库 |
| **JavDb** | 作品列表、热门排行 | curl_cffi + curl 子进程 (绕过 Cloudflare JA3) |
| **Wikipedia/Wikidata** | 个人资料、社交链接 | `wikipediaapi` 库 + 直接 API |
| **sukebei.nyaa.si** | 磁力链接 | httpx + BeautifulSoup |

### 为什么用 curl 而不是 Python requests 访问 JavDb？

JavDb 使用了 Cloudflare Bot Management，它会检测 TLS 指纹（JA3）:
- macOS curl 使用 SecureTransport → 通过
- Python 的 OpenSSL/urllib3 → 被屏蔽
- Playwright 的 BoringSSL → 被屏蔽

方案: 优先使用 `curl_cffi`（模拟浏览器 TLS 指纹），失败时回退 `subprocess curl` + 浏览器 User-Agent 头部，通过 `asyncio.to_thread` 异步调用。

## 配置说明

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `TELEGRAM_BOT_TOKEN` | ✅ | - | Telegram Bot Token |
| `MYSQL_HOST` | | `127.0.0.1` | MySQL 主机 |
| `MYSQL_PORT` | | `3306` | MySQL 端口 |
| `MYSQL_USER` | | `javbot` | MySQL 用户 |
| `MYSQL_PASSWORD` | | `javbot` | MySQL 密码 |
| `MYSQL_DATABASE` | | `javbot` | MySQL 数据库名 |
| `MYSQL_ROOT_PASSWORD` | | - | Docker 初始化用 |
| `HTTP_PROXY` | | - | HTTP 代理 (e.g. `http://host.docker.internal:7890`) |
| `ALLOWED_USER_IDS` | | - | Telegram 用户白名单，逗号分隔；空=不限制 |
| `ADMIN_USER_ID` | | - | 管理员 ID，接收启动通知 |
| `I18N_DEFAULT_LANGUAGE` | | `zh_CN` | 默认语言 (`zh_CN`/`en_US`/`ja_JP`) |
| `LOG_LEVEL` | | `INFO` | 日志等级 |
| `UNCENSORED` | | `0` | `1` 开启无码内容查询 |
| `LATEST_LIMIT` | | `5` | 最新作品返回数量 |
| `TOP_LIMIT` | | `5` | 高分作品返回数量 |
| `SEND_LATEST_COVERS` | | `1` | 是否发送封面图片 |
| `LATEST_COVER_LIMIT` | | `3` | 封面图片数量 |
| `MAGNET_LIMIT` | | `5` | 磁力结果数量 |
| `MAGNET_TIMEOUT` | | `20` | 磁力搜索超时(秒) |
| `RANK_LIMIT_DEFAULT` | | `20` | 排行榜默认数量 |
| `RANK_PAGE_DEFAULT` | | `1` | 排行榜默认页码 |
| `RANK_FEATURE_AVATARS` | | `0` | 排行榜是否展示头像 |
| `RANK_AVATAR_LIMIT` | | `3` | 排行榜头像数量 |
| `RANK_CACHE_TTL` | | `900` | 排行榜缓存 TTL (秒) |
| `PROFILE_CACHE_TTL` | | `1800` | 女优资料缓存 TTL (秒) |
| `PUSH_ENABLED` | | `1` | 开启新作推送功能 |
| `PUSH_CHECK_INTERVAL` | | `3600` | 推送检查间隔 (秒) |
| `PUSH_DIGEST_ENABLED` | | `1` | 开启每日汇总推送 |
| `PUSH_DIGEST_INTERVAL` | | `86400` | 汇总推送检查间隔（秒） |
| `PUSH_BATCH_DELAY` | | `5` | 推送批次间延迟（秒） |
| `MAGNET_CACHE_TTL` | | `300` | 磁力搜索缓存 TTL（秒） |

## 开发

### 依赖

- Python 3.11（`jvav` 原生扩展在 3.13+ 编译失败）
- MySQL 8.0+
- macOS 或 Linux

### 本地运行

```bash
pip install -r requirements.txt
python -m app.main
```

### 测试

```bash
pytest tests/unit/           # 单元测试 (快速、无外部依赖)
pytest tests/service/        # 服务层测试
pytest tests/scraping/       # 爬虫测试 (慢、需外网)
pytest tests/integration/    # 集成测试 (需完整环境)
```

### 代码规范

```bash
flake8 app/ --ignore=E501
mypy app/
black --check app/
isort --check app/
```

## Docker 说明

- Python 3.11-slim 镜像
- 非 root `javbot` 用户运行
- MySQL 8.0 通过 Docker Compose 自动管理
- `data/` 目录需要卷挂载的正确权限

## 许可

MIT
