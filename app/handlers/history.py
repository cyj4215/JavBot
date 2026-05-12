from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..fav_manager import get_favorites_manager
from ..secure_callback import short_callback as _short_callback
from .common import require_auth

if TYPE_CHECKING:
    from telegram import Message, Update

logger = logging.getLogger(__name__)

_DEFAULT_HISTORY_LIMIT = 10


@require_auth
async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared) -> None:
    user = update.effective_user
    limit = _DEFAULT_HISTORY_LIMIT
    if context.args and context.args[0].isdigit():
        limit = min(int(context.args[0]), 50)

    fav_mgr = await get_favorites_manager()
    queries = await fav_mgr.get_recent_favorite_queries(user.id, limit=limit)

    if not queries:
        await msg.reply_text(
            "📜 暂无搜索历史。\n\n"
            "使用 /s 名字 查询女优信息，搜索记录会自动保存。"
        )
        return

    lines = ["<b>\U0001f4dc 最近搜索</b>", f"共 {len(queries)} 条记录", ""]
    keyboard_rows = []

    for idx, q in enumerate(queries, 1):
        name = html.escape(q["actress_name"])
        time_str = q.get("query_time", "")[:16] if q.get("query_time") else ""
        lines.append(f"{idx}. <b>{name}</b>  <i>{time_str}</i>")

        keyboard_rows.append([
            InlineKeyboardButton(
                f"{idx}. {name}",
                callback_data=_short_callback("search", q["actress_name"]),
            )
        ])

    lines.append("")
    lines.append("<i>点击按钮重新查询</i>")

    keyboard = InlineKeyboardMarkup(keyboard_rows + [
        [InlineKeyboardButton("\U0001f504 返回主菜单", callback_data="menu:search")]
    ])

    await msg.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
