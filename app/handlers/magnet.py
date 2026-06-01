from __future__ import annotations

import asyncio
import html
import logging
from typing import TYPE_CHECKING

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..formatters import format_magnet_messages
from ..secure_callback import short_callback as _short_callback, resolve_callback as _resolve_callback
from .common import require_auth, require_auth_callback, send_photo_with_fallback

if TYPE_CHECKING:
    from telegram import Message, Update


async def run_magnet_reply(msg: Message, query: str, shared=None) -> None:
    if shared is None:
        from . import _get_shared
        shared = _get_shared()
    waiting = await msg.reply_text("正在查询，请稍等...")
    timeout = shared.config.magnet_timeout

    # Fetch AV meta (timeout-separated so slow meta doesn't block magnets)
    try:
        av_meta = await asyncio.wait_for(
            asyncio.to_thread(shared.service.get_av_meta, query),
            timeout=timeout,
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("获取番号信息超时: %s", exc)
        av_meta = {}

    # Fetch magnets from JavBus + sukebei
    try:
        items = await asyncio.wait_for(
            asyncio.to_thread(shared.service.get_av_magnets, query, shared.config.magnet_limit),
            timeout=timeout,
        )
    except Exception as exc:
        items = []
        logging.getLogger(__name__).warning("磁力搜索超时: %s", exc)

    from ..fav_manager import get_favorites_manager
    try:
        fav_mgr = await get_favorites_manager()
        await fav_mgr.increment_stat("total_magnet_searches")
    except Exception:
        pass

    lang = shared.service.i18n.DEFAULT_LANG
    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    # Send AV detail card if available
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
        try:
            await waiting.edit_text("正在搜索磁力，请稍等...")
        except Exception:
            pass

    # Send magnet results — per-message try/except so single bad button doesn't lose all
    messages = format_magnet_messages(query, items, _t=_)
    for text, kb in messages:
        try:
            await msg.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=kb)
        except Exception as exc:
            logging.getLogger(__name__).warning("发送磁力结果按钮失败: %s", exc)
            # Fallback: send without keyboard to avoid URL/port rejection
            try:
                await msg.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            except Exception:
                pass


@require_auth
async def magnet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await msg.reply_text("用法：/search 关键词\n例如：/search SSIS-123")
        return
    await run_magnet_reply(msg, query, shared=shared)


@require_auth_callback
async def callback_copymagnet(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    """Handle copymagnet: callback — send full magnet link as text for copy."""
    data = q.data or ""
    magnet_url = _resolve_callback("copymagnet", data)
    if magnet_url is None:
        await q.answer("该链接已过期", show_alert=True)
        return
    await q.answer()
    await q.message.reply_text(
        f"<code>{html.escape(magnet_url)}</code>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
