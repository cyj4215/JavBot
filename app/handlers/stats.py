from __future__ import annotations

from typing import TYPE_CHECKING

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..fav import get_favorites_manager
from .common import _get_lang, require_auth

if TYPE_CHECKING:
    from telegram import Message, Update


_STAT_KEYS = [
    ("total_searches", "stat_total_searches"),
    ("total_profiles_viewed", "stat_profiles_viewed"),
    ("total_magnet_searches", "stat_magnet_searches"),
    ("total_favorites_added", "stat_favorites_added"),
    ("total_favorites_removed", "stat_favorites_removed"),
]


@require_auth
async def stats_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared
) -> None:
    lang = await _get_lang(shared, update)

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    fav_mgr = await get_favorites_manager()
    stats = await fav_mgr.get_all_stats()

    if not stats:
        await msg.reply_text(_("stats_title"))
        return

    lines = [f"<b>📊 {_('stats_title')}</b>", ""]
    for stat_key, label_key in _STAT_KEYS:
        val = stats.get(stat_key, 0)
        lines.append(f"{_(label_key)}: <code>{val}</code>")

    await msg.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )
