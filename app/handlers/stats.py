from __future__ import annotations

from typing import TYPE_CHECKING

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..fav_manager import get_favorites_manager
from .common import _get_lang, require_auth

if TYPE_CHECKING:
    from telegram import Message, Update


_STAT_LABELS = {
    "total_searches": "🔍 搜索次数",
    "total_profiles_viewed": "👩 查看女优资料",
    "total_magnet_searches": "🧲 磁力搜索次数",
    "total_favorites_added": "⭐ 收藏次数",
    "total_favorites_removed": "💔 取消收藏次数",
}

_STAT_LABELS_EN = {
    "total_searches": "🔍 Searches",
    "total_profiles_viewed": "👩 Profiles Viewed",
    "total_magnet_searches": "🧲 Magnet Searches",
    "total_favorites_added": "⭐ Favorites Added",
    "total_favorites_removed": "💔 Favorites Removed",
}

_STAT_LABELS_JA = {
    "total_searches": "🔍 検索回数",
    "total_profiles_viewed": "👩 プロフィール表示",
    "total_magnet_searches": "🧲 マグネット検索",
    "total_favorites_added": "⭐ お気に入り追加",
    "total_favorites_removed": "💔 お気に入り削除",
}


def _labels_for_lang(lang: str) -> dict:
    if lang == "en_US":
        return _STAT_LABELS_EN
    if lang == "ja_JP":
        return _STAT_LABELS_JA
    return _STAT_LABELS


@require_auth
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: Message, shared) -> None:
    user = update.effective_user
    lang = await _get_lang(shared, update)
    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    fav_mgr = await get_favorites_manager()
    stats = await fav_mgr.get_all_stats()
    labels = _labels_for_lang(lang)

    if not stats:
        await msg.reply_text("📊 暂无统计数据。")
        return

    lines = [f"<b>📊 {_('stats_title', 'Statistics')}</b>", ""]
    for key, label in labels.items():
        val = stats.get(key, 0)
        lines.append(f"{label}: <code>{val}</code>")

    await msg.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )
