# 逐条推送消息格式美化设计

- 日期：2026-08-16
- 状态：已批准
- 范围：仅逐条推送（instant push），不动每日汇总（digest）与推送开关消息

## 背景与目标

当前逐条推送（`app/handlers/push.py` 的 `send_new_work_notification`）文案为「标签：值」逐行堆叠：

```
🎉 关注女优更新啦！
👩 女优：三上悠亜
🎬 番号：SSNI-876
📅 日期：2023-05-01
📝 标题：専属女優とイチャイチャ…
```

信息可读，但视觉重心不明确、标题被截断到 80 字、无详情入口。目标：改为**标题置顶式**排版——番号作为视觉焦点，标题用引用块，元数据收成胶囊标签，并新增「查看详情」链接按钮（复用已有 `work.url` 字段，已验证推送路径中该字段有值）。

## 目标格式（定稿：B2 布局 + T2 胶囊标签）

```
🔔 关注的女优有新作品                ← 上下文提示行（i18n push_title，改文案）
🎬 SSNI-876                         ← <b><code>番号</code></b>，加粗+等宽灰底
「専属女優とイチャイチャ同棲生活…」   ← <blockquote> 原生引用块（ptb 21.6 支持）
👩 三上悠亜　📅 2023-05-01          ← <code> 胶囊标签（女优名/日期，全角空格分隔）
```

按钮（一行三枚）：`🔍 搜索磁力`（现有键）＋ `👩 查询`（现有键）＋ `🔗 查看详情`（新键，URL 链接按钮，仅 `work.url` 非空时出现）。

## 架构

### 1. 新增 `app/formatters/push.py`

纯函数模块，仿照 `app/formatters/favorites.py` 模式：

```python
def format_push_notification(
    actress_name: str,
    work: MergedWork,
    _t: Callable[..., str] = lambda k, *a: k,
) -> tuple[str, InlineKeyboardMarkup]:
    """构建逐条推送文案 + 键盘，返回 (caption, keyboard)。"""
```

- 文案拼装、`html.escape`、按钮构建全部收进此函数
- i18n 通过 `_t` 回调注入（与现有 formatter 一致），handler 传入真实翻译函数
- 返回 `(caption_text, keyboard)`，handler 只负责发送

### 2. 修改 `app/handlers/push.py`

`send_new_work_notification` 瘦身为三件事：
1. 查用户语言（现有逻辑不变）
2. 调 `format_push_notification` 得到 `(caption, keyboard)`
3. `send_photo_with_fallback` 发送

删除全部手拼 HTML 逻辑。

### 3. i18n 三语言调整（zh_CN / en_US / ja_JP）

| 键 | 动作 |
|---|---|
| `push_title` | 改文案为上下文行（🔔 关注的女优有新作品 / Your favorite actress has a new work! / お気に入りの新作が出ました！） |
| `push_actress_tag` | 新增「👩 {}」 |
| `push_date_tag` | 新增「📅 {}」 |
| `push_detail_btn` | 新增「🔗 查看详情 / 🔗 Details / 🔗 詳細」 |
| `push_actress`、`push_av_id`、`push_date`、`push_title_label` | 删除（已确认仅旧推送代码引用） |
| `push_unknown`、`push_query_btn`、`search_magnet_for` | 保留不动 |

## 边界处理

| 情况 | 行为 |
|---|---|
| 标题缺失 | 省略引用行 |
| 日期缺失或为「未知」 | 省略日期胶囊 |
| 番号缺失 | 显示「未知」（push_unknown） |
| `work.url` 为空 | 不显示「查看详情」按钮 |
| 标题/女优名含 `<` `>` `&` | `html.escape` 转义，防 HTML 注入 |
| 标题超长 | 截断至 200 字（caption 上限 1024，安全） |
| 封面图加载失败 | 现有 `send_photo_with_fallback` 已处理，不改 |

## 测试

1. `tests/unit/test_formatters.py` 新增 `TestFormatPushNotification`：
   - 完整字段 → 断言上下文行、`<b><code>番号</code></b>`、`<blockquote>`、两个胶囊标签
   - 缺标题 → 无 blockquote；缺日期 → 无日期胶囊
   - 空 url → 无详情按钮；有 url → 按钮存在且链接正确
   - 标题含 `<script>` → 被转义
   - 自定义 `_t` 注入生效
2. `tests/unit/test_handlers_push.py` 现有测试仅断言 `send_message` 调用、不断言文案，改后应保持通过
3. 验证命令：`pytest tests/unit/test_formatters.py tests/unit/test_handlers_push.py -v`

## 明确不做（YAGNI）

- 每日汇总（digest）消息美化——结构不同（按女优分组），后续单独设计
- 推送开关/状态消息美化
- 作品卡片渲染器的通用抽取
