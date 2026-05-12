from __future__ import annotations

import asyncio
import html
import logging
from typing import TYPE_CHECKING

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..formatters import format_magnet_messages
from .common import require_auth, send_photo_with_fallback

if TYPE_CHECKING:
    from telegram import Message, Update


async def run_magnet_reply(msg: Message, query: str) -> None:
    from . import _get_shared

    shared = _get_shared()
    waiting = await msg.reply_text("正在查询，请稍等...")
    try:
        timeout = shared.config.magnet_timeout
        av_meta = await asyncio.wait_for(
            asyncio.to_thread(shared.service.get_av_meta, query),
            timeout=timeout,
        )
        items = await asyncio.wait_for(
            asyncio.to_thread(
                shared.service.get_av_magnets,
                query,
                shared.config.magnet_limit,
            ),
            timeout=timeout,
        )
        from ..fav_manager import get_favorites_manager
        fav_mgr = await get_favorites_manager()
        await fav_mgr.increment_stat("total_magnet_searches")
        lang = shared.service.i18n.DEFAULT_LANG
        def _(key, *a):
            return shared.service.i18n.t(key, lang, *a)

        if av_meta.get("title"):
            detail_lines = ["<b>🎬 作品详情</b>"]
            detail_lines.append(f"<b>番号：</b><code>{html.escape(av_meta['id'])}</code>")
            detail_lines.append(f"<b>标题：</b>{html.escape(av_meta['title'])}")
            if av_meta.get("date") != "未知":
                detail_lines.append(f"<b>日期：</b>{html.escape(av_meta['date'])}")
            try:
                await waiting.delete()
            except Exception:
                pass
            try:
                await send_photo_with_fallback(msg, av_meta.get("img"), "\n".join(detail_lines), shared.config.proxy_addr)
            except Exception:
                logging.getLogger(__name__).warning("发送封面图片失败", exc_info=True)
        else:
            await waiting.edit_text("正在搜索磁力，请稍等...")
        messages = format_magnet_messages(query, items, _t=_)
        for m in messages:
            await msg.reply_text(
                m,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
    except Exception as exc:
        logging.exception("magnet search failed: %s", exc)
        await waiting.edit_text("搜索失败，请稍后再试。")


@require_auth
async def magnet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await msg.reply_text("用法：/search 关键词\n例如：/search SSIS-123")
        return
    await run_magnet_reply(msg, query)
