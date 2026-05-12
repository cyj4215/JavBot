from __future__ import annotations

import html
import logging
import re
from typing import TYPE_CHECKING, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..formatters import format_rankings, build_rank_keyboard
from .common import require_auth, send_photo_with_fallback

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from telegram import CallbackQuery, Message, Update


async def send_rank_avatars_for_page(msg: Message, stars: list[dict[str, Any]], page: int, limit: int) -> None:
    from . import _get_shared

    shared = _get_shared()
    if not shared.config.rank_feature_avatars:
        return
    sent = 0
    for idx, star in enumerate(stars, start=1):
        if sent >= max(1, shared.config.rank_avatar_limit):
            break
        img = (star.get("thumb_url") or star.get("image_url") or "").strip()
        if not img:
            continue
        name = html.escape(star.get("name", "未知"))
        rank_no = (page - 1) * max(1, min(limit, 50)) + idx
        caption = f"<b>#{rank_no} {name}</b>"
        await send_photo_with_fallback(msg, img, caption, shared.config.proxy_addr)
        sent += 1


async def _handle_rank_error(target: Message | CallbackQuery, limit: int, page: int, is_edit: bool = False, loading: bool = False) -> None:
    text = (
        "<b>\U0001f3c6 热门女优排行榜</b>\n"
        "来源：JavDb 排行榜\n\n"
        "⏳ 排行榜数据正在后台加载中，请稍后再试。\n"
        "点击下方按钮重试："
        if loading
        else (
            "<b>\U0001f3c6 热门女优排行榜</b>\n"
            "来源：JavDb 排行榜\n\n"
            "获取榜单失败，请稍后再试。\n"
            "点击下方按钮重试："
        )
    )
    safe_limit = max(1, min(limit, 50))
    safe_page = max(1, min(page, 5))
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f504 重试", callback_data=f"rank_retry:{safe_limit}:{safe_page}")]
    ])
    if is_edit:
        try:
            await target.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        except Exception:
            logger.debug("编辑排行榜消息失败", exc_info=True)
    else:
        await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def _send_rank_result(
    target: Message | CallbackQuery,
    stars: list[dict[str, Any]],
    limit: int,
    page: int,
    with_avatars: bool = False,
    is_edit: bool = False,
    msg: Message | None = None,
    *,
    _t=lambda k, *a: k,
) -> None:
    if not stars:
        from . import _get_shared

        shared = _get_shared()
        cached_stars = shared.service.get_rank_cache(("rank", limit, page))
        if cached_stars:
            text = (
                f"⚠️ 最新数据获取失败，显示缓存数据\n\n{format_rankings(cached_stars, page, _t=_)}"
            )
            kwargs = dict(text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=build_rank_keyboard(limit, page))
            if is_edit:
                await target.edit_message_text(**kwargs)
            else:
                await target.edit_text(**kwargs)
        else:
            await _handle_rank_error(target, limit, page, is_edit=is_edit)
    else:
        kwargs = dict(text=format_rankings(stars, page, _t=_), parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=build_rank_keyboard(limit, page))
        if is_edit:
            await target.edit_message_text(**kwargs)
        else:
            await target.edit_text(**kwargs)
        if with_avatars and msg:
            await send_rank_avatars_for_page(msg, stars, page, limit)


@require_auth
async def rank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    from .common import _get_lang
    lang = await _get_lang(shared, update)
    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)
    limit = shared.config.rank_limit_default
    page = shared.config.rank_page_default
    if len(context.args) >= 1 and context.args[0].isdigit():
        limit = int(context.args[0])
    if len(context.args) >= 2 and context.args[1].isdigit():
        page = int(context.args[1])

    cache_key = ("rank", limit, page)
    has_cache = shared.service.get_rank_cache(cache_key) is not None
    waiting = await msg.reply_text("正在获取热门女优排行榜...")
    try:
        stars = await shared.service.get_hot_star_rankings(limit, page)
        if not stars and not has_cache:
            await _handle_rank_error(waiting, limit, page, loading=True)
        else:
            await _send_rank_result(waiting, stars, limit, page, _t=_)
    except Exception as exc:
        logger.exception("rank fetch failed: %s", exc)
        await _handle_rank_error(waiting, limit, page, loading=not has_cache)


async def rank_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import _get_shared
    from .common import _get_lang, is_allowed

    shared = _get_shared()
    q = update.callback_query
    if not q or not q.message:
        return
    if not is_allowed(update, shared.config.allowed_user_ids):
        await q.answer("无权限使用", show_alert=True)
        return
    lang = await _get_lang(shared, update)
    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)
    data = q.data or ""

    retry_match = re.match(r"^rank_retry:(\d{1,2}):(\d)$", data)
    if retry_match:
        limit = int(retry_match.group(1))
        page = int(retry_match.group(2))
        limit = max(1, min(limit, 50))
        page = max(1, min(page, 5))

        await q.answer("正在重试...")
        try:
            stars = await shared.service.get_hot_star_rankings(limit, page)
            await _send_rank_result(q, stars, limit, page, is_edit=True, _t=_)
        except Exception as exc:
            logger.exception("rank retry failed: %s", exc)
            await _handle_rank_error(q, limit, page, is_edit=True)
        return

    m = re.match(r"^rank:(\d{1,2}):(\d):([01])$", data)
    if not m:
        await q.answer()
        return

    limit = int(m.group(1))
    page = int(m.group(2))
    with_avatars = m.group(3) == "1"
    limit = max(1, min(limit, 50))
    page = max(1, min(page, 5))

    await q.answer("加载中...")
    try:
        stars = await shared.service.get_hot_star_rankings(limit, page)
        await _send_rank_result(q, stars, limit, page, with_avatars=with_avatars, is_edit=True, msg=q.message, _t=_)
    except Exception as exc:
        logger.exception("rank callback failed: %s", exc)
        await _handle_rank_error(q, limit, page, is_edit=True)
