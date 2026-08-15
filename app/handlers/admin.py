"""管理员命令：健康检查。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..fav import get_favorites_manager
from ..health import collect_health

if TYPE_CHECKING:
    from telegram import Update

logger = logging.getLogger(__name__)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import _get_shared

    shared = _get_shared()
    msg = update.effective_message
    if not msg:
        return
    user = update.effective_user
    if not user or user.id != shared.config.admin_user_id:
        await msg.reply_text(shared.service.i18n.t("admin_no_permission"))
        return

    try:
        fav_mgr = await get_favorites_manager()
        text = await collect_health(shared, fav_mgr)
        await msg.reply_text(
            text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
    except Exception as exc:
        logger.exception("admin health check failed: %s", exc)
        await msg.reply_text(shared.service.i18n.t("error_generic"))
