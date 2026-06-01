from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import TYPE_CHECKING, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..fav_manager import get_favorites_manager
from ..formatters import _SORT_LABELS, render_favorites_page
from ..secure_callback import short_callback as _short_callback, resolve_callback as _resolve_callback
from .common import make_t, require_auth, require_auth_callback

if TYPE_CHECKING:
    from telegram import Update


def _fuzzy_match(input_name: str, fav_name: str) -> bool:
    input_lower = input_name.lower().strip()
    fav_lower = fav_name.lower().strip()
    if input_lower == fav_lower:
        return True
    if input_lower in fav_lower or fav_lower in input_lower:
        return True
    return False


def _parse_actress_names(query: str) -> List[str]:
    names = re.split(r'[,;，；]+', query)
    actress_names = []
    for name in names:
        name = name.strip()
        if name:
            actress_names.append(name)
    return actress_names


async def _get_user_favorites(user_id: int):
    """Get favorites for a user. Returns the list or None (with empty favorites message logic)."""
    favorites_manager = await get_favorites_manager()
    result = await favorites_manager.get_favorites(user_id, limit=200)
    favorites = result.get('items', []) if isinstance(result, dict) else result
    if not favorites:
        return None
    return favorites


async def _update_favorite_keyboard(q, is_favorited: bool, actress_name: str) -> None:
    """Create and apply the keyboard update for favorite/unfavorite toggle."""
    if is_favorited:
        new_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐ 已收藏", callback_data=_short_callback("unfavnow", actress_name)),
                InlineKeyboardButton("📰 查看最新作品", callback_data=_short_callback("works", actress_name))
            ]
        ])
    else:
        new_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("☆ 收藏", callback_data=_short_callback("favnow", actress_name)),
                InlineKeyboardButton("📰 查看最新作品", callback_data=_short_callback("works", actress_name))
            ]
        ])
    try:
        if q.message.caption:
            await q.edit_message_caption(reply_markup=new_keyboard)
        else:
            await q.edit_message_reply_markup(reply_markup=new_keyboard)
    except Exception:
        logging.getLogger(__name__).debug(
            "更新收藏按钮失败", exc_info=True
        )


@require_auth
async def favorite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    logger = logging.getLogger(__name__)
    _ = await make_t(shared, update)

    query = " ".join(context.args).strip()
    if not query:
        await msg.reply_text(_("fav_add_usage"))
        return

    actress_names = _parse_actress_names(query)
    logger.info(f"原始查询字符串: {query}")
    logger.info(f"最终的女优名字列表: {actress_names}")
    logger.info(f"女优名字数量: {len(actress_names)}")

    if not actress_names:
        await msg.reply_text(_("fav_no_valid"))
        return

    user = update.effective_user
    favorites_manager = await get_favorites_manager()

    await favorites_manager.sync_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    results = []
    waiting = await msg.reply_text(_("fav_querying", len(actress_names)))
    try:
        for actress_name in actress_names:
            profile = await shared.service.query_profile_async(actress_name)
            if not profile.found:
                results.append(_("fav_found", actress_name))
                continue

            actress_data = {'extra_info': profile.extra_info} if profile.extra_info else None
            success = await favorites_manager.add_favorite(
                user_id=user.id,
                actress_name=profile.star_name,
                actress_id=profile.star_id,
                actress_data=actress_data
            )

            if success:
                results.append(_("fav_added", profile.star_name))
                await favorites_manager.increment_stat("total_favorites_added")
            else:
                results.append(_("fav_add_failed", profile.star_name))

    except Exception as exc:
        from .common import log_handler_error
        log_handler_error(exc, "favorite add failed")
        results.append(_("error_generic"))

    await waiting.edit_text("\n".join(results) + _("fav_myfav_hint"))


@require_auth
async def unfavorite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    logger = logging.getLogger(__name__)
    _ = await make_t(shared, update)

    query = " ".join(context.args).strip()
    if not query:
        await msg.reply_text(_("fav_unfav_usage"))
        return

    actress_names = _parse_actress_names(query)
    logger.info(f"原始查询字符串: {query}")
    logger.info(f"最终的女优名字列表: {actress_names}")
    logger.info(f"女优名字数量: {len(actress_names)}")

    if not actress_names:
        await msg.reply_text(_("fav_no_valid"))
        return

    user = update.effective_user
    favorites_manager = await get_favorites_manager()

    results = []
    waiting = await msg.reply_text(_("fav_unfav_querying", len(actress_names)))
    try:
        for actress_name in actress_names:
            if not await favorites_manager.is_favorite(user.id, actress_name):
                result = await favorites_manager.get_favorites(user.id, limit=100)
                fav_list = result.get('items', []) if isinstance(result, dict) else result
                matched = None
                for fav in fav_list:
                    if _fuzzy_match(actress_name, fav['actress_name']):
                        matched = fav['actress_name']
                        break

                if matched:
                    actress_name = matched
                else:
                    results.append(_("fav_not_found", actress_name))
                    continue

            success = await favorites_manager.remove_favorite(user.id, actress_name)

            if success:
                results.append(_("fav_removed", actress_name))
                await favorites_manager.increment_stat("total_favorites_removed")
            else:
                results.append(_("fav_remove_failed", actress_name))

    except Exception as exc:
        from .common import log_handler_error
        log_handler_error(exc, "favorite remove failed")
        results.append(_("error_generic"))

    await waiting.edit_text("\n".join(results) + "\n\n" + _("fav_list_title") + " /myfav")


@require_auth
async def my_favorites_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared, page: int = 1) -> None:
    user = update.effective_user
    _ = await make_t(shared, update)

    sort = "date"
    if context.args:
        arg = context.args[0].lower()
        if arg in _SORT_LABELS:
            sort = arg

    favorites_per_page = 6
    fav_mgr = await get_favorites_manager()
    favorites = await _get_user_favorites(user.id)
    if not favorites:
        await msg.reply_text(_("fav_empty"))
        return

    last_query_map = await fav_mgr.get_last_query_time_map(user.id)
    text, reply_markup = render_favorites_page(favorites, page, favorites_per_page, sort=sort, last_query_map=last_query_map)

    await msg.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )


@require_auth
async def favorites_latest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    user = update.effective_user
    _ = await make_t(shared, update)

    favorites = await _get_user_favorites(user.id)
    if not favorites:
        await msg.reply_text(_("fav_empty"))
        return

    waiting = await msg.reply_text(f"正在查询 {len(favorites)} 位收藏女优的最新作品...")

    try:
        async def query_actress_latest(fav):
            works = []
            try:
                profile = await shared.service.query_profile_async(fav['actress_name'])
                if profile.found and profile.latest_works:
                    for work in profile.latest_works[:2]:
                        work_copy = dict(work)
                        work_copy['actress_name'] = fav['actress_name']
                        works.append(work_copy)
            except Exception:
                logging.getLogger(__name__).warning(
                    "查询收藏女优最新作品失败: %s", fav.get('actress_name'), exc_info=True
                )
            return works

        tasks = [query_actress_latest(fav) for fav in favorites]
        results_list = await asyncio.gather(*tasks)

        all_latest_works = []
        for works in results_list:
            all_latest_works.extend(works)

        all_latest_works.sort(key=lambda x: x.get('date', ''), reverse=True)

        if not all_latest_works:
            await waiting.edit_text("暂无最新作品信息。")
            return

        await waiting.delete()

        batch_size = 5
        for i in range(0, len(all_latest_works), batch_size):
            batch = all_latest_works[i:i + batch_size]

            lines = ["<b>🎬 收藏女优最新作品</b>", ""]

            for work in batch:
                actress_name = html.escape(work.get('actress_name', '未知'))
                av_id = html.escape(work.get('id', '未知'))
                av_date = html.escape(work.get('date', '未知日期'))
                av_title = html.escape(work.get('title', '')[:40])

                lines.append(f"<b>👩 {actress_name}</b>")
                lines.append(f"🎬 <code>{av_id}</code>")
                if av_date != "未知日期":
                    lines.append(f"📅 {av_date}")
                if av_title:
                    lines.append(f"📝 {av_title}")
                lines.append("")

            if i + batch_size < len(all_latest_works):
                lines.append(f"...还有 {len(all_latest_works) - i - batch_size} 部作品")

            await msg.reply_text(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

    except Exception as exc:
        from .common import log_handler_error
        log_handler_error(exc, "favorites latest works query failed")
        try:
            await waiting.edit_text("查询失败，请稍后再试。")
        except Exception:
            pass


@require_auth_callback
async def callback_favquery(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    """Handle favquery: callback — query actress profile from favorites list."""
    from .search import run_search_reply

    data = q.data or ""
    actress_name = _resolve_callback("favquery", data)
    if actress_name is None:
        _ = await make_t(shared, update)
        await q.answer(_("fav_expired"), show_alert=True)
        return

    fav_mgr = await get_favorites_manager()
    await fav_mgr.record_favorite_query(update.effective_user.id, actress_name)
    await q.answer(f"正在查询 {actress_name}...")
    await run_search_reply(
        q.message, actress_name,
        update.effective_user.id if update.effective_user else None,
        back_data="myfav:page:1:date", shared=shared,
    )


@require_auth_callback
async def callback_favnow(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    """Handle favnow: callback — add actress to favorites."""
    data = q.data or ""
    actress_name = _resolve_callback("favnow", data)
    if actress_name is None:
        _ = await make_t(shared, update)
        await q.answer(_("fav_expired"), show_alert=True)
        return

    fav_mgr = await get_favorites_manager()
    try:
        profile = await shared.service.query_profile_async(actress_name)
        if not profile.found:
            await q.answer(f"未找到女优: {actress_name}", show_alert=True)
            return
        actress_data = {"extra_info": profile.extra_info} if profile.extra_info else None
        user = update.effective_user
        await fav_mgr.sync_user(user_id=user.id, username=user.username,
                                first_name=user.first_name, last_name=user.last_name)
        success = await fav_mgr.add_favorite(user.id, profile.star_name, profile.star_id, actress_data)
        if success:
            await q.answer(f"✅ 已收藏: {profile.star_name}")
            await _update_favorite_keyboard(q, True, profile.star_name)
        else:
            await q.answer("收藏失败", show_alert=True)
    except Exception as exc:
        from .common import log_handler_error
        log_handler_error(exc, "favorite favnow failed")
        await q.answer("收藏失败", show_alert=True)


@require_auth_callback
async def callback_unfavnow(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    """Handle unfavnow: callback — remove actress from favorites."""
    data = q.data or ""
    actress_name = _resolve_callback("unfavnow", data)
    if actress_name is None:
        _ = await make_t(shared, update)
        await q.answer(_("fav_expired"), show_alert=True)
        return

    try:
        success = await (await get_favorites_manager()).remove_favorite(update.effective_user.id, actress_name)
        if success:
            await q.answer(f"✅ 已取消收藏: {actress_name}")
            await _update_favorite_keyboard(q, False, actress_name)
        else:
            await q.answer("取消收藏失败", show_alert=True)
    except Exception as exc:
        from .common import log_handler_error
        log_handler_error(exc, "favorite unfavnow failed")
        await q.answer("取消收藏失败", show_alert=True)


async def _edit_or_send(q, text, reply_markup=None):
    """Edit message text if possible, otherwise send new message (handles photo→text transition)."""
    try:
        if q.message.photo:
            await q.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_web_page_preview=True)
        else:
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception:
        try:
            await q.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception:
            pass


@require_auth_callback
async def callback_myfav_page(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    """Handle myfav:page: callback — paginate favorites list."""
    data = q.data or ""
    parts = data[len("myfav:page:"):].split(":", 1)
    page = int(parts[0])
    sort = parts[1] if len(parts) > 1 else "date"
    await q.answer()

    fav_mgr = await get_favorites_manager()
    favorites = await _get_user_favorites(update.effective_user.id)
    if not favorites:
        _ = await make_t(shared, update)
        await _edit_or_send(q, _("fav_empty"))
        return

    last_query_map = await fav_mgr.get_last_query_time_map(update.effective_user.id)
    text, reply_markup = render_favorites_page(favorites, page, 6, sort=sort, last_query_map=last_query_map)
    await _edit_or_send(q, text, reply_markup)


@require_auth_callback
async def callback_myfav_sort(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    """Handle myfav:sort: callback — cycle sort order in favorites list."""
    data = q.data or ""
    parts = data[len("myfav:sort:"):].split(":", 1)
    current_sort = parts[0]
    page = int(parts[1]) if len(parts) > 1 else 1
    sort_order = ["date", "name", "recent"]
    next_sort = sort_order[(sort_order.index(current_sort) + 1) % len(sort_order)] if current_sort in sort_order else "date"

    fav_mgr = await get_favorites_manager()
    favorites = await _get_user_favorites(update.effective_user.id)
    if not favorites:
        _ = await make_t(shared, update)
        await _edit_or_send(q, _("fav_empty"))
        return

    await q.answer(f"排序切换: {_SORT_LABELS.get(next_sort, next_sort)}")
    last_query_map = await fav_mgr.get_last_query_time_map(update.effective_user.id)
    text, reply_markup = render_favorites_page(favorites, page, 6, sort=next_sort, last_query_map=last_query_map)
    await _edit_or_send(q, text, reply_markup)


@require_auth
async def export_favorites_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    user = update.effective_user
    _ = await make_t(shared, update)
    fav_mgr = await get_favorites_manager()
    data = await fav_mgr.export_favorites(user.id)
    if not data:
        await msg.reply_text(_("fav_export_empty"))
        return

    import io
    file = io.BytesIO(data.encode("utf-8"))
    file.name = f"favorites_{user.id}.json"
    await msg.reply_document(
        document=file,
        filename=file.name,
        caption=_("fav_exported", data.count("actress_name")),
    )
