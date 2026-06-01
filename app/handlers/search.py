from __future__ import annotations

import asyncio
import html
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from telegram import Message, Update

from ..fav_manager import get_favorites_manager
from ..formatters import format_profile, looks_like_av_id
from ..secure_callback import short_callback as _short_callback, resolve_callback as _resolve_callback
from .common import make_t, require_auth, require_auth_callback

_pending_queries: Dict[int, asyncio.Task] = {}


async def send_works_media_group(msg: Message, works: List[Dict[str, Any]], _t, proxy_addr: str = "") -> None:
    """Send each work as separate photo with magnet button. Download covers via curl."""
    from ..improved_utils import download_image_via_curl

    logger = logging.getLogger(__name__)
    for work in works:
        av_id = work.get("id", "")
        img_url = (work.get("img") or "").strip()
        if not img_url or not av_id:
            continue

        caption_parts = [f"<b>🎬 {html.escape(av_id)}</b>"]
        date = (work.get("date") or "").strip()
        title = (work.get("title") or "").strip()[:80]
        if date and date != _t("work_date_unknown"):
            caption_parts.append(f"📅 {html.escape(date)}")
        if title:
            caption_parts.append(f"📝 {html.escape(title)}")

        button = InlineKeyboardMarkup([[InlineKeyboardButton(
            _t("search_magnet_for", av_id),
            callback_data=_short_callback("magnet", av_id),
        )]])

        try:
            img_bytes = await asyncio.to_thread(download_image_via_curl, img_url, proxy_addr)
            if img_bytes:
                await msg.reply_photo(
                    photo=img_bytes,
                    caption="\n".join(caption_parts),
                    parse_mode=ParseMode.HTML,
                    reply_markup=button,
                )
            else:
                await msg.reply_photo(
                    photo=img_url,
                    caption="\n".join(caption_parts),
                    parse_mode=ParseMode.HTML,
                    reply_markup=button,
                )
        except Exception as exc:
            logger.warning("发送作品图片失败: %s", exc, exc_info=True)


async def run_search_reply(msg: Message, query: str, user_id: Optional[int] = None, back_data: Optional[str] = None, shared=None) -> None:
    if shared is None:
        from . import _get_shared
        shared = _get_shared()
    lang = shared.service.i18n.DEFAULT_LANG
    if user_id:
        try:
            fav_mgr = await get_favorites_manager()
            lang = await fav_mgr.get_user_language(user_id)
        except Exception:
            pass

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    cancel_kb = None
    if user_id:
        cancel_data = _short_callback("cancel", str(user_id))
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏹ 取消", callback_data=cancel_data)]])
        task = asyncio.current_task()
        if task:
            _pending_queries[user_id] = task

    waiting: Message = await msg.reply_text(_("search_loading"), reply_markup=cancel_kb)
    try:
        profile = await shared.service.query_profile_async(query)
        fav_mgr = await get_favorites_manager()
        is_fav = False
        if profile.found and profile.star_name is not None and user_id is not None:
            is_fav = await fav_mgr.is_favorite(user_id, profile.star_name)
        base_text, keyboard = format_profile(profile, user_id, is_favorite=is_fav, _t=_, back_data=back_data)

        await fav_mgr.increment_stat("total_searches")
        if profile.found:
            await fav_mgr.increment_stat("total_profiles_viewed")

        await waiting.delete()

        avatar_url = (profile.avatar_url or "").strip() if profile.found else ""
        if avatar_url and len(base_text) < 950:
            try:
                from ..improved_utils import download_image_via_curl
                proxy_addr = shared.config.proxy_addr if hasattr(shared.config, 'proxy_addr') else ""
                avatar_bytes = await asyncio.to_thread(download_image_via_curl, avatar_url, proxy_addr)
                if avatar_bytes:
                    await msg.reply_photo(
                        photo=avatar_bytes,
                        caption=base_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
                else:
                    await msg.reply_photo(
                        photo=avatar_url,
                        caption=base_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
            except Exception:
                await msg.reply_text(
                    base_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                )
        else:
            await msg.reply_text(
                base_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )

        if profile.found and profile.latest_works and shared.config.send_latest_covers:
            await send_works_media_group(msg, profile.latest_works[:shared.config.latest_cover_limit], _, proxy_addr=shared.config.proxy_addr)
    except asyncio.CancelledError:
        try:
            await waiting.edit_text("⏹ " + _("search_cancelled"))
        except Exception:
            pass
        return
    except Exception as exc:
        logging.exception("query failed: %s", exc)
        await waiting.edit_text(_("search_failed"))
    finally:
        if user_id:
            _pending_queries.pop(user_id, None)


@require_auth
async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared) -> None:
    args: List[str] = context.args if context.args else []
    query: str = " ".join(args).strip()
    if not query:
        _ = await make_t(shared, update)
        await msg.reply_text(_("search_usage"))
        return
    user: Optional[Any] = update.effective_user
    await run_search_reply(msg, query, user.id if user else None, shared=shared)


@require_auth
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared) -> None:
    from .magnet import run_magnet_reply

    if not msg.text:
        return

    query: str = msg.text.strip()
    if not query:
        return

    if looks_like_av_id(query):
        await run_magnet_reply(msg, query, shared=shared)
        return

    user: Optional[Any] = update.effective_user
    await run_search_reply(msg, query, user.id if user else None, shared=shared)


@require_auth_callback
async def cancel_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    data = q.data or ""
    uid_str = _resolve_callback("cancel", data)
    if uid_str is None:
        await q.answer("该操作已过期", show_alert=True)
        return

    caller_id = update.effective_user.id
    if int(uid_str) != caller_id:
        await q.answer("无权取消他人的查询", show_alert=True)
        return

    task = _pending_queries.pop(caller_id, None)
    if task and not task.done():
        task.cancel()
        await q.answer("已取消")
        await q.edit_message_text("⏹ 已取消查询")
    else:
        await q.answer("没有正在进行的查询")
