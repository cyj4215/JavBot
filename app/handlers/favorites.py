from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import TYPE_CHECKING, Any, List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..favorites import get_favorites_manager
from ..secure_callback import short_callback as _short_callback, resolve_callback as _resolve_callback
from .common import require_auth, require_auth_callback

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


def _render_favorites_page(favorites: list[dict[str, Any]], page: int, favorites_per_page: int) -> Tuple[str, InlineKeyboardMarkup]:
    total_favorites = len(favorites)
    total_pages = (total_favorites + favorites_per_page - 1) // favorites_per_page
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * favorites_per_page
    end_idx = start_idx + favorites_per_page
    page_favorites = favorites[start_idx:end_idx]

    lines = ["<b>📚 我的收藏</b>", ""]

    for idx, fav in enumerate(page_favorites, start_idx + 1):
        actress_name = html.escape(fav['actress_name'])
        created_at = fav['created_at'][:10] if fav['created_at'] else "未知"
        lines.append(f"{idx}. {actress_name} (收藏于: {created_at})")

    lines.append("")
    lines.append(f"共收藏 {total_favorites} 位女优")
    if total_pages > 1:
        lines.append(f"第 {page}/{total_pages} 页")
    lines.append("")
    lines.append("点击名字可快速查询最新作品：")
    lines.append("使用 /favlatest 查看所有收藏女优的最新作品")

    keyboard = []
    row = []
    for idx, fav in enumerate(page_favorites, start_idx + 1):
        actress_name = fav['actress_name']
        display_name = actress_name[:15] + "..." if len(actress_name) > 15 else actress_name
        row.append(InlineKeyboardButton(
            f"{idx}. {display_name}",
            callback_data=_short_callback("favquery", actress_name)
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    if total_pages > 1:
        page_buttons = []
        if page > 1:
            page_buttons.append(InlineKeyboardButton("◀️ 上一页", callback_data=f"myfav:page:{page-1}"))
        if page < total_pages:
            page_buttons.append(InlineKeyboardButton("下一页 ▶️", callback_data=f"myfav:page:{page+1}"))
        if page_buttons:
            keyboard.append(page_buttons)

    keyboard.append([InlineKeyboardButton("📰 查看所有收藏的最新作品", callback_data="favlatest:all")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    return "\n".join(lines), reply_markup


_EMPTY_FAVORITES_MSG = (
    "你还没有收藏任何女优。\n\n"
    "使用 /fav 女优名字 来收藏女优\n"
    "例如：/fav 三上悠亚"
)


def _get_user_favorites(user_id: int):
    """Get favorites for a user. Returns the list or None (with empty favorites message logic)."""
    favorites_manager = get_favorites_manager()
    result = favorites_manager.get_favorites(user_id, limit=100)
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
                InlineKeyboardButton("📰 查看最新作品", callback_data=_short_callback("favquery", actress_name))
            ]
        ])
    else:
        new_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("☆ 收藏", callback_data=_short_callback("favnow", actress_name)),
                InlineKeyboardButton("📰 查看最新作品", callback_data=_short_callback("favquery", actress_name))
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

    query = " ".join(context.args).strip()
    if not query:
        await msg.reply_text("用法：/fav 女优名字\n例如：/fav 三上悠亚\n支持一次性添加多个女优，用逗号或分号分隔\n例如：/fav 三上悠亚, 苍井空; 波多野结衣")
        return

    actress_names = _parse_actress_names(query)
    logger.info(f"原始查询字符串: {query}")
    logger.info(f"最终的女优名字列表: {actress_names}")
    logger.info(f"女优名字数量: {len(actress_names)}")

    if not actress_names:
        await msg.reply_text("未找到有效的女优名字")
        return

    user = update.effective_user
    favorites_manager = get_favorites_manager()

    favorites_manager.sync_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    results = []
    waiting = await msg.reply_text(f"正在查询 {len(actress_names)} 位女优...")
    try:
        for actress_name in actress_names:
            profile = await shared.service.query_profile_async(actress_name)
            if not profile.found:
                results.append(f"❌ 未找到女优: {actress_name}")
                continue

            actress_data = {'extra_info': profile.extra_info} if profile.extra_info else None
            success = favorites_manager.add_favorite(
                user_id=user.id,
                actress_name=profile.star_name,
                actress_id=profile.star_id,
                actress_data=actress_data
            )

            if success:
                results.append(f"✅ 已收藏: {profile.star_name}")
            else:
                results.append(f"❌ 收藏失败: {profile.star_name}")

    except Exception as exc:
        logging.exception("收藏失败: %s", exc)
        results.append(f"❌ 收藏失败: {str(exc)}")

    await waiting.edit_text("\n".join(results) + "\n\n使用 /myfav 查看所有收藏\n使用 /favlatest 查看收藏女优的最新作品")


@require_auth
async def unfavorite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    logger = logging.getLogger(__name__)

    query = " ".join(context.args).strip()
    if not query:
        await msg.reply_text("用法：/unfav 女优名字\n例如：/unfav 三上悠亚\n支持一次性取消多个收藏，用逗号或分号分隔\n例如：/unfav 三上悠亚, 苍井空; 波多野结衣")
        return

    actress_names = _parse_actress_names(query)
    logger.info(f"原始查询字符串: {query}")
    logger.info(f"最终的女优名字列表: {actress_names}")
    logger.info(f"女优名字数量: {len(actress_names)}")

    if not actress_names:
        await msg.reply_text("未找到有效的女优名字")
        return

    user = update.effective_user
    favorites_manager = get_favorites_manager()

    results = []
    waiting = await msg.reply_text(f"正在取消收藏 {len(actress_names)} 位女优...")
    try:
        for actress_name in actress_names:
            if not favorites_manager.is_favorite(user.id, actress_name):
                result = favorites_manager.get_favorites(user.id, limit=100)
                fav_list = result.get('items', []) if isinstance(result, dict) else result
                matched = None
                for fav in fav_list:
                    if _fuzzy_match(actress_name, fav['actress_name']):
                        matched = fav['actress_name']
                        break

                if matched:
                    actress_name = matched
                else:
                    results.append(f"❌ 未找到收藏: {actress_name}")
                    continue

            success = favorites_manager.remove_favorite(user.id, actress_name)

            if success:
                results.append(f"✅ 已取消收藏: {actress_name}")
            else:
                results.append(f"❌ 取消收藏失败: {actress_name}")

    except Exception as exc:
        logging.exception("取消收藏失败: %s", exc)
        results.append(f"❌ 取消收藏失败: {str(exc)}")

    await waiting.edit_text("\n".join(results) + "\n\n使用 /myfav 查看所有收藏")


@require_auth
async def my_favorites_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared, page: int = 1) -> None:
    user = update.effective_user

    favorites_per_page = 10
    favorites = _get_user_favorites(user.id)
    if not favorites:
        await msg.reply_text(_EMPTY_FAVORITES_MSG)
        return

    text, reply_markup = _render_favorites_page(favorites, 1, favorites_per_page)

    await msg.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )


@require_auth
async def favorites_latest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    user = update.effective_user

    favorites = _get_user_favorites(user.id)
    if not favorites:
        await msg.reply_text(_EMPTY_FAVORITES_MSG)
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
            batch = all_latest_works[i:i+batch_size]

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
        logging.exception("查询收藏最新作品失败: %s", exc)
        await waiting.edit_text("查询失败，请稍后再试。")


@require_auth_callback
async def favorite_query_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    from .search import run_search_reply

    data = q.data or ""

    if data.startswith("myfav:page:"):
        logging.info(f"收到分页回调: {data}")
        page = int(data[len("myfav:page:"):])
        await q.answer()
        user = update.effective_user

        favorites_per_page = 10
        favorites = _get_user_favorites(user.id)
        if not favorites:
            await q.edit_message_text(_EMPTY_FAVORITES_MSG)
            return

        text, reply_markup = _render_favorites_page(favorites, page, favorites_per_page)

        await q.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        return

    if data.startswith("favquery:"):
        actress_name = _resolve_callback("favquery", data)

        if actress_name is None:
            await q.answer("该链接已过期，请重新点击收藏列表中的女优名字", show_alert=True)
            return

        user = update.effective_user
        favorites_manager = get_favorites_manager()

        favorites_manager.record_favorite_query(user.id, actress_name)

        await q.answer(f"正在查询 {actress_name}...")
        user = update.effective_user
        await run_search_reply(q.message, actress_name, user.id if user else None)

    elif data.startswith("favnow:"):
        actress_name = _resolve_callback("favnow", data)
        if actress_name is None:
            await q.answer("该链接已过期，请重新搜索", show_alert=True)
            return
        user = update.effective_user
        favorites_manager = get_favorites_manager()

        favorites_manager.sync_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        try:
            profile = await shared.service.query_profile_async(actress_name)
            if not profile.found:
                await q.answer(f"未找到女优: {actress_name}", show_alert=True)
                return

            actress_data = {'extra_info': profile.extra_info} if profile.extra_info else None
            success = favorites_manager.add_favorite(
                user_id=user.id,
                actress_name=profile.star_name,
                actress_id=profile.star_id,
                actress_data=actress_data
            )

            if success:
                await q.answer(f"✅ 已收藏: {profile.star_name}")
                await _update_favorite_keyboard(q, True, profile.star_name)
            else:
                await q.answer("收藏失败", show_alert=True)

        except Exception as exc:
            logging.exception("即时收藏失败: %s", exc)
            await q.answer("收藏失败", show_alert=True)

    elif data.startswith("unfavnow:"):
        actress_name = _resolve_callback("unfavnow", data)
        if actress_name is None:
            await q.answer("该链接已过期，请重新搜索", show_alert=True)
            return
        user = update.effective_user
        favorites_manager = get_favorites_manager()

        success = favorites_manager.remove_favorite(user.id, actress_name)

        if success:
            await q.answer(f"✅ 已取消收藏: {actress_name}")
            await _update_favorite_keyboard(q, False, actress_name)
        else:
            await q.answer("取消收藏失败", show_alert=True)

    elif data == "favlatest:all":
        await q.answer("正在查询所有收藏的最新作品...")
        await favorites_latest_cmd(update, context)
