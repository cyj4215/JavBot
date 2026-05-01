from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from telegram import Message, Update

from ..favorites import get_favorites_manager
from ..formatters import format_profile, looks_like_av_id
from ..secure_callback import short_callback as _short_callback
from .common import require_auth, send_photo_with_fallback


async def run_search_reply(msg: Message, query: str, user_id: Optional[int] = None) -> None:
    from . import _get_shared

    shared = _get_shared()
    waiting: Message = await msg.reply_text("查询中，请稍等...")
    try:
        profile = await shared.service.query_profile_async(query)
        is_fav = (
            profile.found
            and profile.star_name is not None
            and user_id is not None
            and get_favorites_manager().is_favorite(user_id, profile.star_name)
        )
        base_text, keyboard = format_profile(profile, user_id, is_favorite=is_fav)

        await waiting.delete()

        await msg.reply_text(
            base_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )

        if shared.config.send_latest_covers and profile.found and profile.latest_works:
            for work in profile.latest_works[:shared.config.latest_cover_limit]:
                if not work.get("id"):
                    continue

                img: str = (work.get("img") or "").strip()
                av_id: str = (work.get("id") or "").strip()
                av_date: str = (work.get("date") or "未知").strip()
                av_title: str = (work.get("title") or "").strip()[:80]

                work_lines: List[str] = [
                    f"<b>🎬 {html.escape(av_id)}</b>"
                ]
                if av_date != "未知":
                    work_lines.append(f"📅 出品时间：{html.escape(av_date)}")
                if av_title:
                    work_lines.append(f"📝 {html.escape(av_title)}")

                work_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🧲 搜索 {av_id} 磁力", callback_data=_short_callback("magnet", av_id))]
                ])

                work_caption: str = "\n".join(work_lines)

                if img:
                    await send_photo_with_fallback(msg, img, work_caption, shared.config.proxy_addr, reply_markup=work_keyboard)
    except Exception as exc:
        logging.exception("query failed: %s", exc)
        await waiting.edit_text("查询失败，请稍后再试。")


@require_auth
async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared) -> None:
    args: List[str] = context.args if context.args else []
    query: str = " ".join(args).strip()
    if not query:
        await msg.reply_text("用法：/s 名字\n例如：/s 三上悠亚")
        return
    user: Optional[Any] = update.effective_user
    await run_search_reply(msg, query, user.id if user else None)


@require_auth
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared) -> None:
    from .magnet import run_magnet_reply

    if not msg.text:
        return

    query: str = msg.text.strip()
    if not query:
        return

    if looks_like_av_id(query):
        await run_magnet_reply(msg, query)
        return

    user: Optional[Any] = update.effective_user
    await run_search_reply(msg, query, user.id if user else None)
