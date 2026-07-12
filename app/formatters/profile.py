from __future__ import annotations

import html
from collections.abc import Callable
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..models.profile import ActressProfile
from ..secure_callback import short_callback as _short_callback


def format_profile(
    profile: ActressProfile,
    user_id: int | None = None,
    *,
    is_favorite: bool = False,
    _t: Callable[..., str] = lambda k, *a: k,
    back_data: str | None = None,
) -> tuple[str, InlineKeyboardMarkup | None]:
    def esc(s: str | None, quote: bool = False) -> str:
        return html.escape(s, quote=quote) if s else ""

    if not profile.found:
        query = esc(profile.query)
        lines = [
            "<b>🔍 " + _t("search_result") + "</b>",
            _t("search_no_result", query),
        ]
        if profile.suggestions:
            lines.append("")
            lines.append("<b>💡 " + _t("search_suggestions") + "</b>")
            keyboard_rows = []
            row = []
            for _idx, name in enumerate(profile.suggestions[:8], 1):
                row.append(
                    InlineKeyboardButton(name, callback_data=_short_callback("search", name))
                )
                if len(row) == 2:
                    keyboard_rows.append(row)
                    row = []
            if row:
                keyboard_rows.append(row)
            keyboard_rows.append(
                [InlineKeyboardButton(_t("menu_return"), callback_data="menu:search")]
            )
            lines.append("")
            lines.append(_t("search_click_button"))
            return "\n".join(lines), InlineKeyboardMarkup(keyboard_rows)
        else:
            lines.append("")
            lines.append(_t("search_try_full_name"))
            lines.append("")
            lines.append(_t("search_usage"))
            no_result_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton(_t("menu_return"), callback_data="menu:search")]]
            )
            return "\n".join(lines), no_result_markup

    star_name = esc(profile.star_name)
    star_id = esc(profile.star_id)
    lines = [
        "<b>👩 " + _t("profile_title") + "</b>",
        f"<b>{_t('profile_name')}</b><code>{star_name}</code>",
        f"<b>{_t('profile_id')}</b><code>{star_id}</code>",
    ]
    if profile.matched_name and profile.matched_name != profile.query:
        lines.append(f"<b>{_t('profile_match')}</b>{esc(profile.matched_name)}")
    if profile.wiki_url:
        title = esc(profile.wiki_title or profile.star_name)
        wiki_url = esc(profile.wiki_url, quote=True)
        lines.append(f'<b>{_t("profile_wiki")}</b><a href="{wiki_url}">{title}</a>')
    if profile.extra_info:
        birth_date = esc(profile.extra_info.birth_date)
        height = esc(profile.extra_info.height)
        measurements = esc(profile.extra_info.measurements)
        cup = esc(profile.extra_info.cup)
        socials = profile.extra_info.socials
        if birth_date or height or measurements or cup or socials:
            lines.append("")
            lines.append("<b>" + _t("profile_bio") + "</b>")
            if birth_date:
                lines.append(_t("profile_birth", birth_date))
            if height:
                lines.append(_t("profile_height", height))
            if measurements:
                lines.append(_t("profile_measurements", measurements))
            if cup:
                lines.append(_t("profile_cup", cup))
            if socials:
                links = []
                for s in socials[:6]:
                    label = esc(s.label)
                    url = esc(s.url, quote=True)
                    if url:
                        links.append(f'<a href="{url}">{label}</a>')
                if links:
                    lines.append(_t("profile_social") + " | ".join(links))

    lines.append("")
    lines.append(f"<i>{_t('bot_data_source')}</i>")
    lines.append(f"<i>{_t('bot_query_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</i>")

    result_keyboard = []
    if user_id is not None and profile.found and profile.star_name:
        star_name_value = profile.star_name

        if is_favorite:
            result_keyboard.append(
                [
                    InlineKeyboardButton(
                        _t("profile_favorited"),
                        callback_data=_short_callback("unfavnow", star_name_value),
                    ),
                    InlineKeyboardButton(
                        _t("profile_latest_works"),
                        callback_data=_short_callback("works", star_name_value),
                    ),
                ]
            )
        else:
            result_keyboard.append(
                [
                    InlineKeyboardButton(
                        _t("profile_favorite"),
                        callback_data=_short_callback("favnow", star_name_value),
                    ),
                    InlineKeyboardButton(
                        _t("profile_latest_works"),
                        callback_data=_short_callback("works", star_name_value),
                    ),
                ]
            )

        if back_data:
            result_keyboard.append(
                [
                    InlineKeyboardButton("← " + _t("profile_back_fav"), callback_data=back_data),
                ]
            )
        result_keyboard.append(
            [InlineKeyboardButton(_t("menu_return"), callback_data="menu:search")]
        )

    return "\n".join(lines), InlineKeyboardMarkup(result_keyboard) if result_keyboard else None
