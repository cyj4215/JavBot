"""Interactive works browser — paginated work cards from profile cache."""
from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any, Dict, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..secure_callback import short_callback as _short_callback, resolve_callback as _resolve_callback
from .common import require_auth_callback

if TYPE_CHECKING:
    from telegram import Update

logger = logging.getLogger(__name__)

_last_works_msg: Dict[int, int] = {}

_MAX_CAPTION = 950


async def _get_profile_works(name: str, shared) -> List[Dict[str, Any]]:
    """Fetch works for star from cache or re-query."""
    try:
        profile = await shared.service.query_profile_async(name)
        if profile.found and profile.latest_works:
            return profile.latest_works
    except Exception as e:
        logger.warning("获取作品失败: %s", e)
    return []


def _build_works_page(
    works: List[Dict[str, Any]],
    star_name: str,
    index: int,
    _t,
) -> tuple[str, InlineKeyboardMarkup | None, str | None]:
    """Render single work. Returns (caption, keyboard, img_url)."""
    if not works:
        return _t("works_empty"), None, None

    total = len(works)
    idx = max(0, min(index, total - 1))
    work = works[idx]
    av_id = work.get("id", "")
    img_url = (work.get("img") or "").strip()
    date = (work.get("date") or "").strip()
    title = (work.get("title") or "").strip()[:80]

    caption_parts = [
        f"<b>🎬 {html.escape(av_id)}</b>",
    ]
    if date:
        caption_parts.append(f"📅 {html.escape(date)}")
    if title:
        caption_parts.append(f"📝 {html.escape(title)}")
    caption_parts.append("")
    caption_parts.append(f"<i>{_t('works_page', idx + 1, total)}</i>")

    keyboard = []
    nav_row = []
    if idx > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=_short_callback("works", f"{star_name}|{idx - 1}")))
    if av_id:
        nav_row.append(InlineKeyboardButton(_t("search_magnet_for", av_id), callback_data=_short_callback("magnet", av_id)))
    if idx < total - 1:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=_short_callback("works", f"{star_name}|{idx + 1}")))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton(_t("profile_latest_works"), callback_data=_short_callback("favquery", star_name)),
    ])

    caption = "\n".join(caption_parts)
    return caption, InlineKeyboardMarkup(keyboard) if keyboard else None, img_url


@require_auth_callback
async def works_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    """Handle works browsing: works:{signed_star_name|index}."""
    from .common import _get_lang

    data = q.data or ""
    raw = _resolve_callback("works", data)
    if raw is None:
        await q.answer("该链接已过期", show_alert=True)
        return

    lang = await _get_lang(shared, update)

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    parts = raw.split("|", 1)
    star_name = parts[0]
    index = int(parts[1]) if len(parts) > 1 else 0

    # Acknowledge button press immediately before any slow ops
    await q.answer()

    works = await _get_profile_works(star_name, shared)
    works = works[:3]
    caption, keyboard, img_url = _build_works_page(works, star_name, index, _)

    if not works:
        return

    if len(caption) > _MAX_CAPTION:
        caption = caption[:_MAX_CAPTION] + "…"

    user_id = update.effective_user.id
    is_photo = bool(q.message.photo)

    if is_photo and img_url:
        from telegram import InputMediaPhoto
        try:
            await q.edit_message_media(
                media=InputMediaPhoto(media=img_url, caption=caption, parse_mode=ParseMode.HTML),
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    if img_url:
        old_id = _last_works_msg.pop(user_id, None) if not is_photo else None
        if old_id:
            try:
                await q.message.chat.delete_message(old_id)
            except Exception:
                pass
        try:
            from ..improved_utils import download_image_via_curl
            proxy = shared.config.proxy_addr if hasattr(shared.config, 'proxy_addr') else ""
            img_bytes = await asyncio.to_thread(download_image_via_curl, img_url, proxy)
        except Exception:
            img_bytes = None
        try:
            photo = img_bytes if img_bytes else img_url
            sent = await q.message.reply_photo(
                photo=photo,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
        except Exception:
            sent = None
        if sent:
            _last_works_msg[user_id] = sent.message_id
            return

    if is_photo:
        await q.edit_message_caption(
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return

    await q.edit_message_text(
        caption,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )
