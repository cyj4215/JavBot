from __future__ import annotations

import html
from collections.abc import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models.actors import ActorSearchResult

_RANK_FALLBACK: dict[str, str] = {
    "rank_prev": "◀️ 上一页",
    "rank_next": "下一页 ▶️",
    "menu_return": "🔄 返回主菜单",
}


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


def build_rank_keyboard(
    limit: int,
    page: int,
    with_avatars: bool = False,
    _t: Callable[..., str] = lambda k, *a: _RANK_FALLBACK.get(k, k),
) -> InlineKeyboardMarkup:
    page = max(1, min(page, 5))
    limit = max(1, min(limit, 50))
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    av = "1" if with_avatars else "0"
    if page > 1:
        nav.append(
            InlineKeyboardButton(_t("rank_prev"), callback_data=f"rank:{limit}:{page - 1}:{av}")
        )
    if page < 5:
        nav.append(
            InlineKeyboardButton(_t("rank_next"), callback_data=f"rank:{limit}:{page + 1}:{av}")
        )
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(_t("menu_return"), callback_data="menu:rank")])
    return InlineKeyboardMarkup(rows)
