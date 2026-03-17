# Telegram + jvav 女优信息查询机器人（Docker）

这个项目会启动一个 Telegram Bot。你给机器人发女优名字，它会返回：

- 基本名称与演员 ID（JavBus）
- 最新作品编号（JavBus）
- 高分作品编号（DMM）
- Wiki 页面链接（如果可找到）

并且支持：

- `/s 名字` 指令查询（便于后续扩展更多命令）
- 中文名查询增强（简繁转换 + Wiki 别名辅助）
- 最新作品附带出品时间
- 最新作品可自动附带封面图片
- `/search 关键词` 搜索磁力（数据源：`sukebei.nyaa.si`，返回前5条）
- `/magnet`、`/m` 是 `/search` 的别名
- `/rank [数量] [页码]` 获取 DMM 官方月榜热门女优排行榜（实时）
- `/rank` 支持分页按钮与“查看本页头像”按钮
- 女优资料页可展示出生日期、身高、三围、罩杯、社媒链接（若可获取）
- Telegram 左下角菜单会自动显示主要命令（启动时自动同步）

## 1. 准备 Telegram Bot Token

先在 Telegram 的 [@BotFather](https://t.me/BotFather) 创建机器人并拿到 token。

## 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填好：

```bash
TELEGRAM_BOT_TOKEN=你的token
```

## 3. Docker 运行

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

停止：

```bash
docker compose down
```

## 4. 使用

给你的机器人发送名字，例如：

- 三上悠亜
- 明日花キララ
- Yua Mikami

或使用命令：

```bash
/s 三上悠亚
/search SSIS-123
/rank 20 1
```

如果你直接发送类似 `SSIS-123` 这种番号格式，也会自动触发磁力搜索。

## 说明

- `jvav` 在 Python 3.13 下依赖编译会失败，所以镜像固定使用 Python 3.11。
- 数据抓取依赖第三方站点可用性，偶尔会超时或变更页面结构。
- 可用环境变量：`LATEST_LIMIT`、`TOP_LIMIT`、`SEND_LATEST_COVERS`、`LATEST_COVER_LIMIT`、`MAGNET_LIMIT`、`MAGNET_TIMEOUT`、`RANK_LIMIT`、`RANK_PAGE`、`SEND_RANK_AVATARS`、`RANK_AVATAR_LIMIT`、`PROFILE_CACHE_TTL`、`RANK_CACHE_TTL`、`UNCENSORED`（设置为1开启无码内容查询，默认0）。
