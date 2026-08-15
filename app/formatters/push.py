from __future__ import annotations

import html
from collections.abc import Callable
from urllib.parse import urlsplit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models import MergedWork
from ..secure_callback import short_callback as _short_callback

_TITLE_MAX = 200
_UNKNOWN_DATE = "未知"  # MergedWork.date 模型的哨兵默认值


def _is_valid_url(url: str) -> bool:
    """Telegram URL buttons require a well-formed http(s) URL."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc) and not any(
        ch.isspace() for ch in url
    )


def format_push_notification(
    actress_name: str,
    work: MergedWork,
    _t: Callable[..., str] = lambda k, *a: k,
) -> tuple[str, InlineKeyboardMarkup]:
    """构建逐条推送的 caption 与键盘，返回 (caption, keyboard)。"""
    av_id = work.id or _t("push_unknown")
    title_raw = (work.title or "").strip()[:_TITLE_MAX]
    date = (work.date or "").strip()

    lines = [
        _t("push_title"),
        f"<b>🎬 <code>{html.escape(av_id)}</code></b>",
    ]
    if title_raw:
        lines.append(f"<blockquote>{html.escape(title_raw)}</blockquote>")

    tags = [html.escape(_t("push_actress_tag", actress_name))]
    if date and date != _UNKNOWN_DATE:
        tags.append(html.escape(_t("push_date_tag", date)))
    lines.append("　".join(f"<code>{tag}</code>" for tag in tags))

    row = [
        InlineKeyboardButton(
            _t("search_magnet_for", av_id),
            callback_data=_short_callback("magnet", av_id),
        ),
        InlineKeyboardButton(
            _t("push_query_btn", actress_name),
            callback_data=_short_callback("favquery", actress_name),
        ),
    ]
    if work.url and len(work.url) <= 256 and _is_valid_url(work.url):
        row.append(InlineKeyboardButton(_t("push_detail_btn"), url=work.url))

    return "\n".join(lines), InlineKeyboardMarkup([row])
