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
    back_data: Optional[str] = None,
) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    def esc(s, quote=False):
        return html.escape(s, quote=quote) if s else ""

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

    lines.append("")
    lines.append(f"<i>{_t('bot_data_source')}</i>")
    lines.append(f"<i>{_t('bot_query_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</i>")

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


def format_magnet_messages(
    query: str,
    items: List[Dict[str, Any]],
    max_len: int = 3900,
    _t: Callable[..., str] = lambda k, *a: k,
) -> List[Tuple[str, Optional[InlineKeyboardMarkup]]]:
    q = html.escape(query)
    if not items:
        return [
            (
                f"{_t('magnet_result')}\n🔍 <code>{q}</code>\n\n{_t('magnet_no_result')}",
                None,
            )
        ]

    messages: List[Tuple[str, Optional[InlineKeyboardMarkup]]] = []
    current_lines = [_t("magnet_result"), f"🔍 <code>{q}</code>", ""]
    current_kb: List[List[InlineKeyboardButton]] = []

    for idx, item in enumerate(items[:5], start=1):
        title = html.escape(item.get("title", ""))[:120]
        size = html.escape(item.get("size", "Unknown"))
        magnet = item.get("magnet", "")
        magnet_hash = magnet.replace("magnet:?xt=urn:btih:", "")[:20] if magnet else ""
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

        if magnet and magnet.startswith("magnet:"):
            current_kb.append([InlineKeyboardButton(
                f"📋 {_t('magnet_copy')} #{idx}",
                callback_data=_short_callback("copymagnet", magnet),
            )])

    current_lines.append(f"<i>{_t('magnet_data_source')}</i>")
    current_lines.append(f"<i>{_t('bot_query_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</i>")
    messages.append(("\n".join(current_lines), InlineKeyboardMarkup(current_kb) if current_kb else None))
    return messages


# ── Favorites page rendering (extracted from handlers/favorites.py) ──

_SORT_LABELS = {"date": "收藏时间", "name": "名称", "recent": "最近查询"}


def time_ago(dt_str: str) -> str:
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return dt_str[:10] if dt_str else ""
    delta = datetime.now() - dt
    if delta.days > 30:
        return f"{delta.days // 30}月前"
    if delta.days > 0:
        return f"{delta.days}天前"
    if delta.seconds >= 3600:
        return f"{delta.seconds // 3600}小时前"
    if delta.seconds >= 60:
        return f"{delta.seconds // 60}分钟前"
    return "刚刚"


def sort_favorites(favorites, sort: str, last_query_map) -> List[Dict[str, Any]]:
    if sort == "name":
        return sorted(favorites, key=lambda f: f["actress_name"].lower())
    if sort == "recent":
        def _sort_key(f):
            t = last_query_map.get(f["actress_name"], "")
            return t if t else "\x00"
        return sorted(favorites, key=_sort_key, reverse=True)
    return sorted(favorites, key=lambda f: (f.get("created_at") or ""), reverse=True)


def render_favorites_page(
    favorites: List[Dict[str, Any]],
    page: int,
    favorites_per_page: int,
    sort: str = "date",
    last_query_map: Dict[str, str] = None,
) -> Tuple[str, InlineKeyboardMarkup]:
    if last_query_map is None:
        last_query_map = {}

    sorted_favs = sort_favorites(favorites, sort, last_query_map)
    total_favorites = len(sorted_favs)
    total_pages = max(1, (total_favorites + favorites_per_page - 1) // favorites_per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * favorites_per_page
    end_idx = start_idx + favorites_per_page
    page_favorites = sorted_favs[start_idx:end_idx]

    sort_label = _SORT_LABELS.get(sort, sort)
    lines = [
        "<b>📚 我的收藏</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"  排序: {sort_label}    共 {total_favorites} 位",
        "",
    ]

    for idx, fav in enumerate(page_favorites, start_idx + 1):
        name = html.escape(fav["actress_name"])
        lines.append(f"  {idx}. <b>{name}</b>")

    lines.append("")
    if total_pages > 1:
        lines.append(f"  第 {page}/{total_pages} 页")

    keyboard = []
    row = []
    for fav in page_favorites:
        name = fav["actress_name"]
        btn_label = name[:10] + "…" if len(name) > 10 else name
        row.append(InlineKeyboardButton(btn_label, callback_data=_short_callback("favquery", name)))
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


def looks_like_av_id(text: str) -> bool:
    q = text.strip().upper()
    return bool(re.search(r"\b[A-Z]{2,8}[-_ ]?\d{2,6}\b", q))


def format_rankings(
    stars: List[Dict[str, Any]],
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
