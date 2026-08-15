# JavBot 缺陷修复与功能完善设计方案

> 日期：2026-08-15
> 状态：审核中
> 关联：承接 `2026-07-12-code-quality-enhancement-design.md`（代码质量改造已落地）

## 概述

在现有功能框架（搜索/资料/作品/磁力/排行/收藏/推送/历史/统计/i18n）基础上，分三层推进：

1. **P1 修复层** — 4 个真实 Bug / 名不副实的功能（推送去重、磁力代理、搜索历史、作品浏览器）
2. **P2 工程层** — i18n 完整化、死代码清理、回调签名规范、文档更新、小修
3. **P3 新功能层** — 推送汇总（digest）、作品详情增强、管理员健康检查

---

## P1 修复层

### F1. 推送去重改为按用户

**问题**：`actress_works` 表以 `(actress_name, av_id)` 唯一键做**全局**去重。多位用户关注同一位女优时，只有检查顺序最靠前的用户能收到新作通知，其余用户永远收不到。

**方案**：

- 新增表 `user_seen_works`：

```sql
CREATE TABLE IF NOT EXISTS user_seen_works (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    av_id VARCHAR(255) NOT NULL,
    actress_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_av (user_id, av_id),
    INDEX idx_usw_created (created_at)
)
```

- `FavoritesManager` 新增 `record_user_work(user_id, actress_name, av_id, title, date, url, img) -> bool`：`INSERT IGNORE` 到 `user_seen_works`，返回 `rowcount > 0` 表示"该用户第一次见这部作品"。
- `handlers/push.py` 的 `check_favorite()` 改用 `record_user_work`（替换 `record_actress_work` 作为推送判定）。
- `actress_works` 表**保留**（历史数据不回滚，留作后续作品信息库复用），不再承担推送去重职责；`record_actress_work` 方法保留。
- 90 天清理 job 同步清理 `user_seen_works`（`scheduler.py` + `cleanup_old_data` 各加一条 DELETE）。

### F2. sukebei 磁力搜索走代理

**问题**：`JavBusService.get_av_magnets()` 每次 `new MagnetSearch()`（无 proxy），而 `ActressService` 中带代理的 `self._magnet_search` 从未被使用。Docker + `HTTP_PROXY` 环境下 sukebei.nyaa.si 大概率不可达，磁力结果只剩 JavBus 一半。

**方案**：

- `ActressService.__init__` 把 `self._magnet_search` 传入 `JavBusService(magnet_search_module=...)` —— 该参数**已存在**，只是从未接线。
- `JavBusService.get_av_magnets()` 改用注入的实例；删除方法内 `from ..magnet_search import MagnetSearch` 的局部实例化。
- 删除 `ActressService._bot_session`（死代码，见 E2）。

### F3. /history 记录所有搜索 + 自动去重

**问题**：`record_favorite_query` 只在收藏列表点击"查询"（`callback_favquery`）时调用，普通 `/s` 搜索、自由文本搜索、番号磁力搜索都不记录，`/history` 名不副实。

**方案**：

- `run_search_reply()` 在 profile 查询成功返回后，调用 `record_favorite_query(user_id, 规范化名字)` 记录普通搜索（含 `/s` 与自由文本路径）。
- `on_text` 走番号磁力搜索路径时，也在 `run_magnet_reply` 中记录番号（query 原样，复用 `record_favorite_query`）。
- **去重**：`record_favorite_query` 插入前先查"最近 24h 内同 `(user_id, actress_name)` 是否有记录"，有则跳过；**移除** `QUERY_FREQUENCY_LIMIT`（同女优每小时 10 次硬上限）——去重窗口取代硬上限：同一名字 24h 内只记一条，不同名字互不影响。
- 历史页展示、分页回调、90 天清理逻辑不变。

### F4. works 浏览器去掉 `works[:3]`

**问题**：`handlers/works.py` 的 `works_callback` 硬编码 `works = works[:3]`，交互式翻页只能浏览 3 部作品，与 profile 的合并作品列表（JavBus 最新 + JavDb 高分）不符。

**方案**：删除该切片，翻页基于完整合并列表。

---

## P2 工程层

### E1. i18n 完整化（三语言全覆盖）

**目标**：所有用户可见文案走 `I18nService`，删除硬编码中文。

- 迁移硬编码文案：`handlers/magnet.py`（"正在查询，请稍等…"、用法提示）、`handlers/favorites.py`（收藏成功/失败提示、查询提示、"暂无最新作品信息"）、`handlers/push.py`（通知模板整段）、`handlers/history.py`、`handlers/works.py`（"该链接已过期"）、`handlers/common.py`（权限提示）、`handlers/search.py`（取消相关）、`handlers/rank.py` 残留。
- `handlers/stats.py` 的 `_STAT_LABELS` / `_STAT_LABELS_EN` / `_STAT_LABELS_JA` 三个 dict 删除，标签并入 `services/i18n/zh_CN.py` / `en_US.py` / `ja_JP.py`。
- 新增 key 三语言全量补齐；en 用英文、ja 用日语，不用中文占位。
- **回归防护**：新增单元测试，用正则从 `app/handlers/*.py` 提取 `_t("...")` / `_("...")` 的 key，断言三语言文件均有定义（注意排除 `t()` 方法定义处的误报）。
- 动态文案（女优名、番号、错误详情）不翻译，仅翻译模板。

### E2. 死代码清理

删除以下（删除前 grep 确认无引用，含 tests/）：

| 文件/字段 | 说明 |
|-----------|------|
| `app/session.py`（BotSession） | 创建后从未使用；httpx AsyncClient 无 shutdown 关闭（资源泄漏隐患） |
| `app/fav/push.py`（PushService） | 与 FavoritesManager 推送方法重复，无调用者 |
| `app/fav/export.py`（FavoriteExportService） | 与 FavoritesManager.export_favorites 重复，无调用者 |
| `ActressService._bot_session` 字段 | 创建后从未使用 |

> 注：`_magnet_search` 字段**不删除**——F2 将其注入 `JavBusService` 后转为正常依赖。`2026-07-12` spec 曾规划 BotSession 作为全局 async session，实际未接线即成为死代码，本次直接删除而非补接线（现有模块均已各自持有会话）。

### E3. 回调签名规范（明文导航回调）

**现状**：`menu:` / `lang:` / `hist:page:` / `rank:` / `rank_retry:` 为明文回调，与 HMAC 签名模型不一致。

**决策**：**不改签名**。理由：这些回调只携带页码/语言代码等无敏感数据；签名存储有容量与单次使用限制，高频页码点击会大量消耗存储。改为：

- 在 `secure_callback.py` 模块 docstring 与 CLAUDE.md 中明确规范：**仅限无敏感数据的 UI 导航回调可明文；携带用户数据/查询内容的一律 HMAC 签名**。
- 统一 `rank.py` 中 `rank:` 与 `rank_retry:` 的解析逻辑（两个正则并存，合并为单一解析函数）。

### E4. 文档更新

- `README.md` 与 `CLAUDE.md` 架构图修正：`formatters.py` → `formatters/` 包、`fav_manager.py` → `fav/`、`i18n_service.py` → `services/i18n/`、删除 `http_utils.py` 引用；补充 `user_seen_works` 表、`push_mode` 列说明。
- `.env.example` 同步新增 N1 相关环境变量。

### E5. 小修

- 排行榜预热使用 `RANK_LIMIT_DEFAULT` 替代硬编码 20（`rank_service._warm_cache` 当前只预热 `("rank", 20, page)`），其他 limit 组合维持"按需冷取 + 缓存"现状，不扩大预热面。
- 推送批次间 `await asyncio.sleep(batch_size)` 硬编码 5s → 改为可配置（`PUSH_BATCH_DELAY`，默认 5）。
- `MAGNET_CACHE_TTL` 移入 `BotConfig`（当前 `magnet_search.py` 直接 `os.getenv`），配置入口统一。

---

## P3 新功能层

### N1. 推送汇总（digest）模式

**交互**：`/push` 扩展为三态：`on`（逐条，默认）/ `digest`（汇总）/ `off`。`/push` 无参数时显示当前状态与内联键盘切换按钮（逐条 / 汇总 / 关闭）。

**存储**：`user_push_settings` 表新增 `push_mode VARCHAR(10) DEFAULT 'instant'`（值：`instant` / `digest` / `off`）。迁移：`_init_tables` 建表语句更新；已存在的库用 `ALTER TABLE ... ADD COLUMN`（先查 `information_schema.COLUMNS` 判断列是否存在，幂等）。`push_enabled` 布尔列保留兼容旧数据：迁移时 `push_enabled=0` → `off`，否则 `instant`。

**行为**：

- `instant`：现状不变（基于 F1 的按用户去重）。
- `digest`：`check_and_push_new_works` 中该用户的新作不即时发送，只写入 `user_seen_works`（标记已见）+ 累积到 digest 队列；每 `PUSH_DIGEST_INTERVAL`（默认 86400s）执行一次汇总发送：按女优分组合并成 1 条消息（封面 + 标题 + 磁力按钮，每组女优最多展示 3 部，超出显示"还有 N 部"），发送后清空队列。
- `off`：不检查、不发送。

**digest 队列存储**：**内存 dict** `{user_id: list[digest_item]}`（`app/handlers/push.py` 模块级或 push 服务内）。重启丢失可接受（最多丢一个周期）。不引入 MySQL 队列表（YAGNI）。

**配置**：`PUSH_DIGEST_ENABLED`（默认 1）、`PUSH_DIGEST_INTERVAL`（默认 86400）。`push.py` 增加 digest 检查 job（`run_repeating`）。

### N2. 作品详情增强

**现状**：`run_magnet_reply` 已有 AV 详情卡（标题/日期/封面），但缺女优信息和动作按钮；磁力为空时无友好引导。

**方案**：

- `JavBusWork` 模型新增 `stars: list[str] = []` 字段（默认空，旧缓存反序列化自动补默认值，无需缓存 schema 迁移）；`JavBusService.get_av_meta` 从 jvav 返回的 av dict 中提取主演名单（键名以 jvav 3.0.0 实际返回为准，取不到则为空列表）。
- 详情卡在 `stars` 非空时展示主演 + "查看女优资料"按钮（`favquery` 签名回调，取第一位主演）。
- 磁力结果为空时：友好提示 + "在 JavBus 查看"链接按钮（`av_meta.url` 已有）。
- 保持现状容错：`av_meta` 失败不阻塞磁力展示。
- **不做**"相关推荐"（需额外数据源，PRD 未列，复杂度高）。

### N3. 管理员健康检查

**交互**：`/admin` 命令，仅 `ADMIN_USER_ID` 可用（独立于 `ALLOWED_USER_IDS` 的权限判断：`config.admin_user_id` 存在且匹配，否则提示无权限）。

**输出**（一条消息）：

- 运行时长（`main.py` 模块级 `START_TIME` 常量）
- 各 TTLCache 实例：条目数、命中率（TTLCache 增加 `hits`/`misses` 内存计数器，`get()` 打点，轻量）
- MySQL：连接池状态（`pool.size` / `pool.free_size`）+ 一次 `SELECT 1` 探活
- 数据源健康：`source_status[source] = (last_ok, last_error)` 内存注册表，在 `javdb_scraper._fetch`、`improved_utils` 下载、`magnet_search`、Wiki 请求处打点（轻量，不引入监控框架）
- 回调存储：复用 `get_callback_store().get_stats()`（已有）
- 最近 50 条 ERROR 日志：`logging.Handler` 子类 + 环形缓冲（`collections.deque(maxlen=50)`），在 `main.py` 注册

**范围控制**：不做 webhook 端点、不做 Prometheus。

---

## 测试策略

- **单元测试**（`tests/unit/`）：
  - F1：`record_user_work` 去重语义（同用户同番号第二次返回 False，不同用户返回 True）
  - F3：`record_favorite_query` 24h 去重；`run_search_reply` 记录路径（mock fav_mgr）
  - E1：i18n key 全量覆盖测试（handler 源码提取 key 断言三语言存在）
  - N1：push_mode 三态逻辑、digest 分组与截断、内存队列清空
  - N3：TTLCache 命中计数、环形日志 handler、`/admin` 权限判断
- **现有测试回归**：全量 `tests/unit/` 通过。
- **手动验证清单**（写进计划）：Docker + 代理下 `/search` 磁力含 sukebei 结果；两个测试账号关注同一女优均能收到推送；`/history` 记录普通搜索；`/admin` 输出正常。

## 回滚策略

| 步骤 | 回滚方式 | 风险 |
|------|---------|------|
| F1 表结构 | 删除 `user_seen_works` 表 + revert 代码 | 低（新表无历史依赖） |
| F2 代理接线 | revert 单文件 | 低 |
| F3 记录逻辑 | revert 单文件 | 低 |
| E1 i18n | revert 单文件 + 保留翻译 key | 低 |
| E2 死代码删除 | `git revert` 恢复文件 | 零 |
| N1 存储变更 | revert 代码 + 保留 `push_mode` 列（无副作用） | 低 |
| N2/N3 | revert 单文件 | 低 |

核心原则：**每个子步骤独立 commit，可单独 revert**。

## 实施顺序

1. **P1 修复层**（F1 → F2 → F3 → F4）：每项独立验证，F1 先行（digest 依赖）
2. **P2 工程层**（E1 → E2 → E5 → E3 → E4）：E1 改动面大放最前，E4 文档最后
3. **P3 新功能层**（N1 → N2 → N3）：N1 依赖 F1
4. 全量回归 + 手动验证清单
