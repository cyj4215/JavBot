from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional, Set, cast

from telegram import InlineKeyboardMarkup, Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from telegram import CallbackQuery

from ..fav_manager import get_favorites_manager
from ..secure_callback import resolve_callback as _resolve_callback


def is_allowed(update: Update, allowed_user_ids: Set[int]) -> bool:
    if not allowed_user_ids:
        return True
    user = update.effective_user
    if not user:
        return False
    return user.id in allowed_user_ids


def _language_context(func: Callable):
    """Decorator: injects _ (i18n lambda) and lang into handler args.

    Handler must have (update, context, msg, shared) signature.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared, *args, **kwargs):
        from . import _get_shared
        shared = _get_shared()
        lang = await _get_lang(shared, update)

        def _(key, *a):
            return shared.service.i18n.t(key, lang, *a)
        return await func(update, context, msg, shared, _, lang, *args, **kwargs)
    return wrapper


async def _get_lang(shared, update) -> str:
    """Get user language setting."""
    user = update.effective_user
    if not user:
        return shared.service.i18n.DEFAULT_LANG
    try:
        fav_mgr = await get_favorites_manager()
        return await fav_mgr.get_user_language(user.id)
    except Exception:
        return shared.service.i18n.DEFAULT_LANG


async def send_photo_with_fallback(
    msg: Message | None = None,
    img_url: Optional[str] = None,
    caption: str = "",
    proxy_addr: str = "",
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    *,
    bot: Any = None,
    chat_id: int | None = None,
) -> None:
    from ..improved_utils import download_image

    async def _send_photo(photo, parse_mode=ParseMode.HTML):
        if bot and chat_id is not None:
            return await bot.send_photo(
                chat_id=chat_id, photo=photo, caption=caption,
                parse_mode=parse_mode, reply_markup=reply_markup,
            )
        return await msg.reply_photo(
            photo=photo, caption=caption,
            parse_mode=parse_mode, reply_markup=reply_markup,
        )

    async def _send_text(parse_mode=ParseMode.HTML):
        if bot and chat_id is not None:
            return await bot.send_message(
                chat_id=chat_id, text=caption,
                parse_mode=parse_mode, reply_markup=reply_markup,
            )
        return await msg.reply_text(
            caption, parse_mode=parse_mode, reply_markup=reply_markup,
        )

    if not img_url:
        await _send_text()
        return

    try:
        img_bytes = await asyncio.to_thread(download_image, img_url, proxy_addr)
        if img_bytes:
            await _send_photo(photo=img_bytes)
        else:
            await _send_photo(photo=img_url)
    except Exception:
        logging.getLogger(__name__).debug("发送图片失败，回退到文本", exc_info=True)
        await _send_text()


def require_auth(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from . import _get_shared

        shared = _get_shared()
        msg = update.effective_message
        if not msg:
            return
        if not is_allowed(update, shared.config.allowed_user_ids):
            await msg.reply_text("无权限使用此机器人。")
            return
        return await func(update, context, msg, shared, *args, **kwargs)
    return wrapper


def require_auth_callback(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from . import _get_shared

        shared = _get_shared()
        q = update.callback_query
        if not q or not q.message:
            return
        if not is_allowed(update, shared.config.allowed_user_ids):
            await q.answer("无权限使用", show_alert=True)
            return
        return await func(update, context, q, shared, *args, **kwargs)
    return wrapper


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import _get_shared

    shared = _get_shared()
    msg: Optional[Message] = update.effective_message
    if not msg:
        return

    if not is_allowed(update, shared.config.allowed_user_ids):
        await msg.reply_text("无权限使用此机器人。")
        return

    lang = await _get_lang(shared, update)

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    text = _("bot_welcome")
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(_("menu_search_actress"), callback_data="menu:search"),
            InlineKeyboardButton(_("menu_magnet"), callback_data="menu:magnet")
        ],
        [
            InlineKeyboardButton(_("menu_rank"), callback_data="menu:rank"),
            InlineKeyboardButton(_("menu_favorites"), callback_data="menu:favorites")
        ],
        [
            InlineKeyboardButton(_("menu_help"), callback_data="menu:help")
        ]
    ])
    await msg.reply_text(text, reply_markup=keyboard)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import _get_shared

    shared = _get_shared()
    msg: Optional[Message] = update.effective_message
    if not msg:
        return

    if not is_allowed(update, shared.config.allowed_user_ids):
        await msg.reply_text("无权限使用此机器人。")
        return

    lang = await _get_lang(shared, update)

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    await msg.reply_text(
        "可用命令：\n"
        "/s 名字 - " + _("search_actress").split("\n")[0] + "\n"
        "/rank - " + _("rank_title") + "\n"
        "/history - 搜索历史\n"
        "/language - 切换语言\n\n"
        "/search 关键词 - " + _("magnet_result") + "\n"
        "/magnet 关键词 - " + _("magnet_result") + "\n"
        "/m 关键词 - " + _("magnet_result") + "\n\n"
        "收藏功能：\n"
        "/fav 名字 - 收藏\n"
        "/unfav 名字 - 取消收藏\n"
        "/myfav - " + _("fav_list_title") + "\n"
        "/favlatest - 查看收藏女优最新作品\n"
        "/exportfav - 导出收藏\n\n"
        "支持直接发送名字查询。\n"
        "发送番号自动搜索磁力。\n"
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import _get_shared
    from .search import run_search_reply
    from .magnet import run_magnet_reply
    from .favorites import my_favorites_cmd
    from .rank import rank_cmd

    shared = _get_shared()
    q: Optional[CallbackQuery] = update.callback_query
    if not q or not q.message:
        return

    msg = cast(Message, q.message)

    if not is_allowed(update, shared.config.allowed_user_ids):
        await q.answer("无权限使用", show_alert=True)
        return

    lang = await _get_lang(shared, update)

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    data = q.data or ""

    if data.startswith("menu:"):
        action = data[len("menu:"):]

        if action == "search":
            await q.answer(_("search_actress").split("\n")[0])
            await msg.reply_text(_("search_actress"))
        elif action == "magnet":
            await q.answer(_("magnet_result"))
            await msg.reply_text(_("magnet_usage"))
        elif action == "favorites":
            await q.answer(_("fav_list_title"))
            await my_favorites_cmd(update, context)
        elif action == "rank":
            await q.answer(_("rank_title"))
            await rank_cmd(update, context)
        elif action == "help":
            await q.answer(_("menu_help"))
            await help_cmd(update, context)
        else:
            await q.answer()
    elif data.startswith("search:"):
        query = _resolve_callback("search", data)
        if query is None:
            await q.answer(_("fav_expired"), show_alert=True)
            return
        await q.answer(f"🔍 {query}")
        user_id: Optional[int] = update.effective_user.id if update.effective_user else None
        await run_search_reply(msg, query, user_id)
    elif data.startswith("magnet:"):
        query = _resolve_callback("magnet", data)
        if query is None:
            await q.answer(_("fav_expired"), show_alert=True)
            return
        await q.answer(f"🧲 {query}")
        await run_magnet_reply(msg, query)
