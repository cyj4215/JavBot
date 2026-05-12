from __future__ import annotations

import html
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from .models import ActressProfile

from .secure_callback import short_callback as _short_callback


def format_profile(
    profile: ActressProfile,
    user_id: Optional[int] = None,
    *,
    is_favorite: bool = False,
    _t: Callable[..., str] = lambda k, *a: k,
) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    def esc(s): return html.escape(s) if s else ""

    if not profile.found:
        query = esc(profile.query)
        lines = [
            "<b>🔍 " + _t("search_result") + "</b>",
            _t("search_no_result", query),
        ]
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
        birth_date = esc(profile.extra_info.get("birth_date", ""))
        height = esc(profile.extra_info.get("height", ""))
        measurements = esc(profile.extra_info.get("measurements", ""))
        cup = esc(profile.extra_info.get("cup", ""))
        socials = profile.extra_info.get("socials", [])
        if birth_date or height or measurements or cup or socials:
            lines.append("")
            lines.append("<b>" + _t("profile_bio") + "</b>")
            if birth_date:
                lines.append(_t("profile_birth", birth_date))
            if height:
                lines.append(_t("profile_height", height))
            if measurements:
                lines.append(_t("profile_measurements", measurements))
            if cup:
                lines.append(_t("profile_cup", cup))
            if socials:
                links = []
                for s in socials[:6]:
                    label = esc(s.get("label", "链接"))
                    url = esc(s.get("url", ""), quote=True)
                    if url:
                        links.append(f"<a href=\"{url}\">{label}</a>")
                if links:
                    lines.append(_t("profile_social") + " | ".join(links))
    if profile.top_ids:
        lines.append("")
        lines.append("<b>" + _t("profile_top_works") + "</b>")
        lines.extend([f"• <code>{esc(i)}</code>" for i in profile.top_ids])

    lines.append("")
    lines.append(f"<i>{_t('bot_data_source')}</i>")
    lines.append(f"<i>{_t('bot_query_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</i>")

    result_keyboard = []
    if user_id is not None and profile.found and profile.star_name:
        star_name_value = profile.star_name

        if is_favorite:
            result_keyboard.append([
                InlineKeyboardButton(_t("profile_favorited"), callback_data=_short_callback("unfavnow", star_name_value)),
                InlineKeyboardButton(_t("profile_latest_works"), callback_data=_short_callback("favquery", star_name_value)),
            ])
        else:
            result_keyboard.append([
                InlineKeyboardButton(_t("profile_favorite"), callback_data=_short_callback("favnow", star_name_value)),
                InlineKeyboardButton(_t("profile_latest_works"), callback_data=_short_callback("favquery", star_name_value)),
            ])

        result_keyboard.append([
            InlineKeyboardButton(_t("magnet_result"), callback_data=_short_callback("magnet", star_name))
        ])

        result_keyboard.append([
            InlineKeyboardButton(_t("menu_return"), callback_data="menu:search")
        ])

    return "\n".join(lines), InlineKeyboardMarkup(result_keyboard) if result_keyboard else None


def format_magnet_messages(
    query: str,
    items: List[Dict[str, Any]],
    max_len: int = 3900,
    _t: Callable[..., str] = lambda k, *a: k,
) -> List[str]:
    q = html.escape(query)
    if not items:
        return [
            _t("magnet_result") + "\n"
            f"🔍 <code>{q}</code>\n\n"
            + _t("magnet_no_result")
        ]

    messages: List[str] = []
    current_lines = [_t("magnet_result"), f"🔍 <code>{q}</code>", ""]

    for idx, item in enumerate(items[:5], start=1):
        title = html.escape(item.get("title", ""))[:120]
        size = html.escape(item.get("size", "Unknown"))
        magnet = html.escape(item.get("magnet", ""))
        block_lines = [
            f"<b>🎯 {idx}. {title}</b>",
            f"{_t('magnet_size')}<code>{size}</code>",
            f"{_t('magnet_link')}<code>{magnet}</code>",
            "",
        ]

        candidate = "\n".join(current_lines + block_lines + [f"<i>{_t('magnet_data_source')}</i>"])
        if len(candidate) > max_len and len(current_lines) > 3:
            current_lines.append(f"<i>{_t('magnet_data_source')}</i>")
            messages.append("\n".join(current_lines))
            current_lines = [
                _t("magnet_continue"),
                f"🔍 <code>{q}</code>",
                "",
            ] + block_lines
        else:
            current_lines.extend(block_lines)

    current_lines.append(f"<i>{_t('magnet_data_source')}</i>")
    current_lines.append(f"<i>{_t('bot_query_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</i>")
    messages.append("\n".join(current_lines))
    return messages


def looks_like_av_id(text: str) -> bool:
    q = text.strip().upper()
    return bool(re.search(r"\b[A-Z]{2,8}[-_ ]?\d{2,6}\b", q))


def format_rankings(
    stars: List[Dict[str, Any]],
    page: int,
    _t: Callable[..., str] = lambda k, *a: k,
) -> str:
    if not stars:
        return _t("rank_empty")

    lines = [
        _t("rank_title"),
        _t("rank_source", page),
        "",
    ]
    start = (page - 1) * 20 + 1
    for idx, star in enumerate(stars, start=start):
        name = html.escape(star.get("name", "未知"))
        actress_id = star.get("id", "")
        id_str = f" ({html.escape(actress_id)})" if actress_id else ""
        lines.append(f"  {idx}. <b>{name}</b>{id_str}")

    lines.append("")
    lines.append(f"<i>{_t('bot_data_source')}</i>")
    return "\n".join(lines)


def build_rank_keyboard(limit: int, page: int) -> InlineKeyboardMarkup:
    page = max(1, min(page, 5))
    limit = max(1, min(limit, 50))
    rows: List[List[InlineKeyboardButton]] = []
    nav: List[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ 上一页", callback_data=f"rank:{limit}:{page-1}:0"))
    if page < 5:
        nav.append(InlineKeyboardButton("下一页 ▶️", callback_data=f"rank:{limit}:{page+1}:0"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔄 返回主菜单", callback_data="menu:rank")])
    return InlineKeyboardMarkup(rows)
