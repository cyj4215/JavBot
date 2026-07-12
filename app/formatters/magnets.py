from __future__ import annotations

import html
from collections.abc import Callable
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models.magnets import MagnetLink
from ..secure_callback import short_callback as _short_callback


def format_magnet_messages(
    query: str,
    items: list[MagnetLink],
    max_len: int = 3900,
    _t: Callable[..., str] = lambda k, *a: k,
) -> list[tuple[str, InlineKeyboardMarkup | None]]:
    q = html.escape(query)
    if not items:
        return [
            (
                f"{_t('magnet_result')}\n🔍 <code>{q}</code>\n\n{_t('magnet_no_result')}",
                None,
            )
        ]

    messages: list[tuple[str, InlineKeyboardMarkup | None]] = []
    current_lines = [_t("magnet_result"), f"🔍 <code>{q}</code>", ""]
    current_kb: list[list[InlineKeyboardButton]] = []

    for idx, item in enumerate(items[:5], start=1):
        title = html.escape(item.title)[:120]
        size = html.escape(item.size)
        magnet = item.magnet
        magnet_hash = magnet.replace("magnet:?xt=urn:btih:", "")[:20] if magnet else ""
        block_lines = [
            f"<b>🎯 {idx}. {title}</b>",
            f"{_t('magnet_size')}<code>{size}</code>",
            f"{_t('magnet_link')}<code>{magnet_hash}</code>",
            "",
        ]

        candidate = "\n".join(current_lines + block_lines + [f"<i>{_t('magnet_data_source')}</i>"])
        if len(candidate) > max_len and len(current_lines) > 3:
            current_lines.append(f"<i>{_t('magnet_data_source')}</i>")
            messages.append(
                ("\n".join(current_lines), InlineKeyboardMarkup(current_kb) if current_kb else None)
            )
            current_lines = [
                _t("magnet_continue"),
                f"🔍 <code>{q}</code>",
                "",
            ] + block_lines
            current_kb = []
        else:
            current_lines.extend(block_lines)

        if magnet and magnet.startswith("magnet:"):
            current_kb.append(
                [
                    InlineKeyboardButton(
                        f"📋 {_t('magnet_copy')} #{idx}",
                        callback_data=_short_callback("copymagnet", magnet),
                    )
                ]
            )

    current_lines.append(f"<i>{_t('magnet_data_source')}</i>")
    current_lines.append(
        f"<i>{_t('bot_query_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</i>"
    )
    messages.append(
        ("\n".join(current_lines), InlineKeyboardMarkup(current_kb) if current_kb else None)
    )
    return messages
