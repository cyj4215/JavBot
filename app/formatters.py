from __future__ import annotations

import html
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from .service import ActressProfile

from .secure_callback import short_callback, resolve_callback


def format_profile(
    profile: ActressProfile, user_id: Optional[int] = None, *, is_favorite: bool = False
) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    if not profile.found:
        query = html.escape(profile.query)
        lines = [
            "<b>🔍 查询结果</b>",
            f"❌ 未找到：<code>{query}</code>",
        ]
        if profile.suggestions:
            lines.append("")
            lines.append("<b>💡 你可能想查：</b>")
            keyboard_rows: List[List[InlineKeyboardButton]] = []
            row: List[InlineKeyboardButton] = []
            for idx, name in enumerate(profile.suggestions[:8], 1):
                row.append(InlineKeyboardButton(name, callback_data=_short_callback("search", name)))
                if len(row) == 2:
                    keyboard_rows.append(row)
                    row = []
            if row:
                keyboard_rows.append(row)
            keyboard_rows.append([InlineKeyboardButton("🔄 返回主菜单", callback_data="menu:search")])
            lines.append("")
            lines.append("点击下方按钮快速查询：")
            return "\n".join(lines), InlineKeyboardMarkup(keyboard_rows)
        else:
            lines.append("")
            lines.append("💡 请尝试中文全名、日文名或英文名。")
            lines.append("")
            lines.append("用法：<code>/s 名字</code>")
            no_result_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 返回主菜单", callback_data="menu:search")]
            ])
            return "\n".join(lines), no_result_markup

    star_name = html.escape(profile.star_name or "")
    star_id = html.escape(profile.star_id or "")
    lines = [
        f"<b>👩 女优信息</b>",
        f"<b>🎯 姓名：</b><code>{star_name}</code>",
        f"<b>🆔 演员ID：</b><code>{star_id}</code>",
    ]
    if profile.matched_name and profile.matched_name != profile.query:
        lines.append(f"<b>🔍 匹配关键词：</b>{html.escape(profile.matched_name)}")
    if profile.wiki_url:
        title = html.escape(profile.wiki_title or profile.star_name or "")
        wiki_url = html.escape(profile.wiki_url, quote=True)
        lines.append(f"<b>📚 Wiki：</b><a href=\"{wiki_url}\">{title}</a>")
    if profile.extra_info:
        birth_date = html.escape(profile.extra_info.get("birth_date", ""))
        height = html.escape(profile.extra_info.get("height", ""))
        measurements = html.escape(profile.extra_info.get("measurements", ""))
        cup = html.escape(profile.extra_info.get("cup", ""))
        socials = profile.extra_info.get("socials", [])
        if birth_date or height or measurements or cup or socials:
            lines.append("")
            lines.append("<b>📋 个人简介</b>")
            if birth_date:
                lines.append(f"• 🎂 出生日期：{birth_date}")
            if height:
                lines.append(f"• 📏 身高：{height}")
            if measurements:
                lines.append(f"• 👙 三围：{measurements}")
            if cup:
                lines.append(f"• 🚺 罩杯：{cup}")
            if socials:
                links = []
                for s in socials[:6]:
                    label = html.escape(s.get("label", "链接"))
                    url = html.escape(s.get("url", ""), quote=True)
                    if url:
                        links.append(f"<a href=\"{url}\">{label}</a>")
                if links:
                    lines.append("• 🌐 社媒：" + " | ".join(links))
    if profile.top_ids:
        lines.append("")
        lines.append("<b>🏆 高分作品</b>")
        lines.extend([f"• <code>{html.escape(i)}</code>" for i in profile.top_ids])

    lines.append("")
    lines.append("<i>🔧 数据来源：JavBus / JavDb / Wikipedia</i>")
    lines.append(f"<i>⏰ 查询时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>")

    result_keyboard: List[List[InlineKeyboardButton]] = []
    if user_id is not None and profile.found and profile.star_name:
        star_name_value = profile.star_name or ""

        if is_favorite:
            result_keyboard.append([
                InlineKeyboardButton("⭐ 已收藏", callback_data=_short_callback("unfavnow", star_name_value)),
                InlineKeyboardButton("📰 查看最新作品", callback_data=_short_callback("favquery", star_name_value))
            ])
        else:
            result_keyboard.append([
                InlineKeyboardButton("☆ 收藏", callback_data=_short_callback("favnow", star_name_value)),
                InlineKeyboardButton("📰 查看最新作品", callback_data=_short_callback("favquery", star_name_value))
            ])

        result_keyboard.append([
            InlineKeyboardButton("💾 搜索磁力", callback_data=_short_callback("magnet", star_name))
        ])

        result_keyboard.append([
            InlineKeyboardButton("🏠 返回主菜单", callback_data="menu:search")
        ])

    return "\n".join(lines), InlineKeyboardMarkup(result_keyboard) if result_keyboard else None


def format_magnet_messages(
    query: str, items: List[Dict[str, Any]], max_len: int = 3900
) -> List[str]:
    q = html.escape(query)
    if not items:
        return [
            "<b>💾 磁力搜索</b>\n"
            f"🔍 关键词：<code>{q}</code>\n\n"
            "❌ 未找到结果。\n"
            "💡 试试：换关键词、用完整番号、或使用日文名。"
        ]

    messages: List[str] = []
    current_lines = ["<b>💾 磁力搜索</b>", f"🔍 关键词：<code>{q}</code>", ""]

    for idx, item in enumerate(items[:5], start=1):
        title = html.escape(item.get("title", ""))[:120]
        size = html.escape(item.get("size", "Unknown"))
        magnet = html.escape(item.get("magnet", ""))
        block_lines = [
            f"<b>🎯 {idx}. {title}</b>",
            f"📦 大小：<code>{size}</code>",
            f"🧲 磁力：<code>{magnet}</code>",
            "",
        ]

        candidate = "\n".join(current_lines + block_lines + ["<i>🔧 数据来源：sukebei.nyaa.si</i>"])
        if len(candidate) > max_len and len(current_lines) > 3:
            current_lines.append("<i>🔧 数据来源：sukebei.nyaa.si</i>")
            messages.append("\n".join(current_lines))
            current_lines = [
                "<b>💾 磁力搜索（续）</b>",
                f"🔍 关键词：<code>{q}</code>",
                "",
            ] + block_lines
        else:
            current_lines.extend(block_lines)

    current_lines.append("<i>🔧 数据来源：sukebei.nyaa.si</i>")
    current_lines.append(f"<i>⏰ 查询时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>")
    messages.append("\n".join(current_lines))
    return messages


def looks_like_av_id(text: str) -> bool:
    q = text.strip().upper()
    return bool(re.search(r"\b[A-Z]{2,8}[-_ ]?\d{2,6}\b", q))


def format_rankings(stars: List[Dict[str, Any]], page: int) -> str:
    if not stars:
        return (
            "<b>🏆 热门女优排行榜</b>\n"
            "📊 来源：JavDb 排行榜\n\n"
            "❌ 暂时无法获取榜单，请稍后再试。"
        )

    lines = [
        "<b>🏆 热门女优排行榜</b>",
        f"📊 来源：JavDb 排行榜（第{page}页）",
        "",
        "<b>🌟 排名列表：</b>",
    ]
    for idx, star in enumerate(stars, start=1):
        name = html.escape(star.get("name", ""))
        if idx <= 3:
            medals = ["🥇", "🥈", "🥉"]
            lines.append(f"{medals[idx-1]} {idx}. {name}")
        else:
            lines.append(f"⭐ {idx}. {name}")
    lines.append("")
    lines.append(f"<i>⏰ 抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>")
    lines.append("<i>🔧 数据来源：JavDb 排行榜</i>")
    return "\n".join(lines)


def build_rank_keyboard(limit: int, page: int) -> InlineKeyboardMarkup:
    page = max(1, min(page, 5))
    limit = max(1, min(limit, 50))
    rows: List[List[InlineKeyboardButton]] = []
    nav: List[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"rank:{limit}:{page - 1}:0"))
    if page < 5:
        nav.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"rank:{limit}:{page + 1}:0"))
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton("🖼️ 查看本页头像", callback_data=f"rank:{limit}:{page}:1"),
        ]
    )
    return InlineKeyboardMarkup(rows)
