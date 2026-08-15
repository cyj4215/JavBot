from __future__ import annotations

import asyncio
import contextlib
import html
import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..formatters import format_magnet_messages
from ..secure_callback import resolve_callback as _resolve_callback
from ..secure_callback import short_callback as _short_callback
from ..services.text_utils import normalize_name
from .common import make_t, require_auth, require_auth_callback, send_photo_with_fallback

if TYPE_CHECKING:
    from telegram import Message, Update


async def run_magnet_reply(
    msg: Message, query: str, shared=None, user_id: int | None = None
) -> None:
    if shared is None:
        from . import _get_shared

        shared = _get_shared()

    lang = shared.service.i18n.DEFAULT_LANG

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    waiting = await msg.reply_text(_("magnet_loading"))
    timeout = shared.config.magnet_timeout

    # Fetch AV meta (timeout-separated so slow meta doesn't block magnets)
    try:
        av_meta = await asyncio.wait_for(
            asyncio.to_thread(shared.service.get_av_meta, query),
            timeout=timeout,
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("获取番号信息超时: %s", exc)
        av_meta = None

    # Fetch magnets from JavBus + sukebei
    try:
        items = await asyncio.wait_for(
            asyncio.to_thread(shared.service.get_av_magnets, query, shared.config.magnet_limit),
            timeout=timeout,
        )
    except Exception as exc:
        items = []
        logging.getLogger(__name__).warning("磁力搜索超时: %s", exc)

    from ..fav import get_favorites_manager

    try:
        fav_mgr = await get_favorites_manager()
        await fav_mgr.increment_stat("total_magnet_searches")
        if user_id is not None:
            await fav_mgr.record_favorite_query(user_id, normalize_name(query))
    except Exception:
        pass

    # Send AV detail card if available
    if av_meta and av_meta.title:
        detail_lines = [f"<b>{_('magnet_detail_title')}</b>"]
        detail_lines.append(
            f"<b>{_('magnet_av_id_label')}</b><code>{html.escape(av_meta.id)}</code>"
        )
        detail_lines.append(f"<b>{_('magnet_title_label')}</b>{html.escape(av_meta.title)}")
        if av_meta.date and av_meta.date != "未知" and av_meta.date != _("work_date_unknown"):
            detail_lines.append(f"<b>{_('magnet_date_label')}</b>{html.escape(av_meta.date)}")
        detail_kb: list[list[InlineKeyboardButton]] = []
        if av_meta.stars:
            first_star = av_meta.stars[0]
            detail_lines.append(
                f"<b>{_('magnet_stars', html.escape('、'.join(av_meta.stars[:5])))}</b>"
            )
            detail_kb.append(
                [
                    InlineKeyboardButton(
                        _("magnet_view_actress"),
                        callback_data=_short_callback("favquery", first_star),
                    )
                ]
            )
        with contextlib.suppress(Exception):
            await waiting.delete()
        try:
            await send_photo_with_fallback(
                msg,
                av_meta.img,
                "\n".join(detail_lines),
                shared.config.proxy_addr,
                reply_markup=InlineKeyboardMarkup(detail_kb) if detail_kb else None,
            )
        except Exception:
            logging.getLogger(__name__).warning("发送封面图片失败", exc_info=True)
    else:
        with contextlib.suppress(Exception):
            await waiting.edit_text(_("magnet_searching"))

    # Send magnet results — per-message try/except so single bad button doesn't lose all
    messages = format_magnet_messages(query, items, _t=_)
    if not items and av_meta and av_meta.url:
        # 空结果 + 有详情页 → 用带链接按钮的引导消息替换无按钮提示
        messages = [
            (
                _("magnet_no_result"),
                InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                _("magnet_open_javbus"),
                                url=av_meta.url,
                            )
                        ]
                    ]
                ),
            )
        ]
    for text, kb in messages:
        try:
            await msg.reply_text(
                text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=kb
            )
        except Exception as exc:
            logging.getLogger(__name__).warning("发送磁力结果按钮失败: %s", exc)
            # Fallback: send without keyboard to avoid URL/port rejection
            with contextlib.suppress(Exception):
                await msg.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@require_auth
async def magnet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    _ = await make_t(shared, update)
    query = " ".join(context.args).strip()
    if not query:
        await msg.reply_text(_("magnet_usage"))
        return
    user = update.effective_user
    await run_magnet_reply(msg, query, shared=shared, user_id=user.id if user else None)


@require_auth_callback
async def callback_copymagnet(
    update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared
) -> None:
    """Handle copymagnet: callback — send full magnet link as text for copy."""
    _ = await make_t(shared, update)
    data = q.data or ""
    magnet_url = _resolve_callback("copymagnet", data)
    if magnet_url is None:
        await q.answer(_("fav_expired"), show_alert=True)
        return
    await q.answer()
    await q.message.reply_text(
        f"<code>{html.escape(magnet_url)}</code>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
