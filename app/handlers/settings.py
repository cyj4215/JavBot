from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..fav_manager import get_favorites_manager
from .common import require_auth

if TYPE_CHECKING:
    from telegram import Message, Update

logger = logging.getLogger(__name__)


@require_auth
async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared) -> None:
    user = update.effective_user
    fav_mgr = await get_favorites_manager()

    if not context.args:
        current_lang = await fav_mgr.get_user_language(user.id)
        lang_name = shared.service.i18n.supported_languages().get(current_lang, current_lang)
        usage = shared.service.i18n.t("lang_usage", current_lang)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("中文", callback_data="lang:zh_CN")],
            [InlineKeyboardButton("English", callback_data="lang:en_US")],
            [InlineKeyboardButton("日本語", callback_data="lang:ja_JP")],
            [InlineKeyboardButton(
                shared.service.i18n.t("menu_return", current_lang),
                callback_data="menu:help"
            )],
        ])

        await msg.reply_text(
            f"🌐 {shared.service.i18n.t('lang_current', current_lang, lang_name)}\n\n{usage}",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return

    lang = context.args[0].strip()
    if not shared.service.i18n.is_supported(lang):
        supported = ", ".join(shared.service.i18n.supported_languages().keys())
        await msg.reply_text(
            shared.service.i18n.t("lang_invalid", "zh_CN", supported),
        )
        return

    await fav_mgr.set_user_language(user.id, lang)
    lang_name = shared.service.i18n.supported_languages().get(lang, lang)
    await msg.reply_text(shared.service.i18n.t("lang_set", lang, lang_name))


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import _get_shared
    from .common import is_allowed

    shared = _get_shared()
    q = update.callback_query
    if not q or not q.message:
        return
    if not is_allowed(update, shared.config.allowed_user_ids):
        await q.answer(shared.service.i18n.t("no_permission_alert"), show_alert=True)
        return

    data = q.data or ""
    if not data.startswith("lang:"):
        await q.answer()
        return

    lang = data[5:]
    if not shared.service.i18n.is_supported(lang):
        await q.answer()
        return

    user = update.effective_user
    fav_mgr = await get_favorites_manager()
    await fav_mgr.set_user_language(user.id, lang)

    lang_name = shared.service.i18n.supported_languages().get(lang, lang)
    await q.answer(shared.service.i18n.t("lang_set", lang, lang_name))
    await q.edit_message_text(
        f"✅ {shared.service.i18n.t('lang_set', lang, lang_name)}",
    )
