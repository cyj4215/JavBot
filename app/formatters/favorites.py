from __future__ import annotations

import html
import re
from collections.abc import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models.favorites import FavoriteEntry
from ..secure_callback import short_callback as _short_callback

_FALLBACK_LABELS: dict[str, str] = {
    "fav_list_title": "我的收藏",
    "sort_label": "排序: {}",
    "fav_total": "共 {} 位",
    "fav_page_info": "第 {}/{} 页",
    "sort_date": "收藏时间",
    "sort_name": "名称",
    "sort_recent": "最近查询",
}


def sort_favorites(
    favorites: list[FavoriteEntry], sort: str, last_query_map: dict[str, str]
) -> list[FavoriteEntry]:
    if sort == "name":
        return sorted(favorites, key=lambda f: f.actress_name.lower())
    if sort == "recent":

        def _sort_key(f: FavoriteEntry) -> str:
            t = last_query_map.get(f.actress_name, "")
            return t if t else "\x00"

        return sorted(favorites, key=_sort_key, reverse=True)
    return sorted(favorites, key=lambda f: f.created_at or "", reverse=True)


def render_favorites_page(
    favorites: list[FavoriteEntry],
    page: int,
    favorites_per_page: int,
    sort: str = "date",
    last_query_map: dict[str, str] | None = None,
    _t: Callable[..., str] = lambda k, *a: (
        _FALLBACK_LABELS.get(k, k).format(*a) if a else _FALLBACK_LABELS.get(k, k)
    ),
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
        name = fav.actress_name
        btn_label = name[:10] + "…" if len(name) > 10 else name
        row.append(InlineKeyboardButton(btn_label, callback_data=_short_callback("favquery", name)))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"myfav:page:{page - 1}:{sort}"))
    nav_row.append(
        InlineKeyboardButton(f"↕️{sort_label}", callback_data=f"myfav:sort:{sort}:{page}")
    )
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"myfav:page:{page + 1}:{sort}"))
    keyboard.append(nav_row)

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def looks_like_av_id(text: str) -> bool:
    q = text.strip().upper()
    return bool(re.search(r"\b[A-Z]{2,8}[-_ ]?\d{2,6}\b", q))
