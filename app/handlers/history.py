from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..fav import get_favorites_manager
from ..formatters import looks_like_av_id
from ..secure_callback import short_callback as _short_callback
from .common import make_t, require_auth

if TYPE_CHECKING:
    from telegram import Message, Update

logger = logging.getLogger(__name__)

_HISTORY_PER_PAGE = 10
_MAX_HISTORY = 50


def _render_history_page(
    queries: list[dict],
    page: int,
    total: int,
    _t=lambda k, *a: k,
) -> tuple[str, InlineKeyboardMarkup]:
    total_pages = max(1, (total + _HISTORY_PER_PAGE - 1) // _HISTORY_PER_PAGE)
    page = max(1, min(page, total_pages))

    start = (page - 1) * _HISTORY_PER_PAGE
    end = start + _HISTORY_PER_PAGE
    page_queries = queries[start:end]

    lines = [
        f"<b>{_t('history_title')}</b>",
        _t("history_total", total),
        "",
    ]
    for idx, q in enumerate(page_queries, start + 1):
        name = html.escape(q["actress_name"])
        time_str = q.get("query_time", "")[:16] if q.get("query_time") else ""
        lines.append(f"{idx}. <b>{name}</b>  <i>{time_str}</i>")

    if total_pages > 1:
        lines.append("")
        lines.append(_t("fav_page_info", page, total_pages))

    lines.append("")
    lines.append(_t("history_hint"))

    keyboard = []
    for q in page_queries:
        name = q["actress_name"]
        btn_label = name[:14] + "…" if len(name) > 14 else name
        prefix = "magnet" if looks_like_av_id(name) else "search"
        keyboard.append(
            [InlineKeyboardButton(f"🔍 {btn_label}", callback_data=_short_callback(prefix, name))]
        )

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"hist:page:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"hist:page:{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(_t("menu_return"), callback_data="menu:search")])

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


@require_auth
async def history_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared
) -> None:
    user = update.effective_user
    _ = await make_t(shared, update)
    page = 1
    if context.args and context.args[0].lstrip("-").isdigit():
        page = max(1, int(context.args[0]))

    fav_mgr = await get_favorites_manager()
    queries = await fav_mgr.get_recent_favorite_queries(user.id, limit=_MAX_HISTORY)

    if not queries:
        await msg.reply_text(_("history_empty"))
        return

    text, markup = _render_history_page(queries, page, len(queries), _t=_)

    await msg.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
        disable_web_page_preview=True,
    )


async def history_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import _get_shared
    from .common import is_allowed, make_t

    shared = _get_shared()
    q = update.callback_query
    if not q or not q.message:
        return

    _ = await make_t(shared, update)
    if not is_allowed(update, shared.config.allowed_user_ids):
        await q.answer(_("no_permission_alert"), show_alert=True)
        return

    data = q.data or ""
    page = int(data.replace("hist:page:", ""))
    user = update.effective_user

    fav_mgr = await get_favorites_manager()
    queries = await fav_mgr.get_recent_favorite_queries(user.id, limit=_MAX_HISTORY)

    if not queries:
        await q.edit_message_text(_("history_empty"))
        return

    await q.answer()
    text, markup = _render_history_page(queries, page, len(queries), _t=_)

    await q.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
        disable_web_page_preview=True,
    )
