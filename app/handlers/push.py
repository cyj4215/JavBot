from __future__ import annotations

import asyncio
import html
import logging
from typing import TYPE_CHECKING, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..fav_manager import get_favorites_manager
from ..secure_callback import short_callback as _short_callback
from .common import require_auth, send_photo_with_fallback

if TYPE_CHECKING:
    from telegram import Bot, Update

logger = logging.getLogger(__name__)

_MAX_CONCURRENT_QUERIES = 5


async def check_and_push_new_works(context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import _get_shared

    shared = _get_shared()
    try:
        if not shared.config.push_enabled_global:
            logger.info("推送功能全局关闭，跳过检查")
            return

        logger.info("开始检查新作品推送")
        favorites_manager = await get_favorites_manager()

        try:
            user_ids = await favorites_manager.get_users_with_push_enabled()
            logger.info(f"找到 {len(user_ids)} 个开启推送的用户")
        except Exception as e:
            logger.error(f"获取推送用户列表失败: {e}")
            return

        sem = asyncio.Semaphore(_MAX_CONCURRENT_QUERIES)
        batch_size = 5
        total_users = len(user_ids)
        new_works_total = 0
        users_with_new_works = 0

        async def check_user(user_id: int) -> list[dict[str, Any]]:
            if shared.config.allowed_user_ids and user_id not in shared.config.allowed_user_ids:
                return []

            try:
                result = await favorites_manager.get_favorites(user_id, limit=100)
                favorites = result.get("items", []) if isinstance(result, dict) else result
            except Exception as e:
                logger.error(f"获取用户 {user_id} 收藏失败: {e}")
                return []

            async def check_favorite(fav: dict) -> list[dict]:
                actress_name = fav.get("actress_name")
                if not actress_name:
                    return []

                try:
                    async with sem:
                        profile = await shared.service.query_profile_async(actress_name)

                    if not profile.found or not profile.latest_works:
                        return []

                    new_works = []
                    for work in profile.latest_works:
                        av_id = work.get("id")
                        if not av_id:
                            continue
                        try:
                            is_new = await favorites_manager.record_actress_work(
                                actress_name=actress_name,
                                av_id=av_id,
                                title=work.get("title"),
                                date=work.get("date"),
                                url=work.get("url"),
                                img=work.get("img"),
                            )
                            if is_new:
                                logger.info(f"发现新作品: {actress_name} - {av_id}")
                                new_works.append({"actress_name": actress_name, "work": work})
                        except Exception as e:
                            logger.error(f"记录作品 {actress_name} - {av_id} 失败: {e}")
                    return new_works
                except Exception as e:
                    logger.error(f"检查女优 {actress_name} 失败: {e}")
                    return []

            user_results = await asyncio.gather(*[check_favorite(fav) for fav in favorites])
            new_works_for_user = [w for r in user_results for w in r]

            if new_works_for_user:
                for item in new_works_for_user:
                    try:
                        await send_new_work_notification(context.bot, user_id, item["actress_name"], item["work"])
                    except Exception as e:
                        logger.error(f"推送作品给用户 {user_id} 失败: {e}")

            try:
                await favorites_manager.update_last_check(user_id)
            except Exception as e:
                logger.error(f"更新用户 {user_id} 检查时间失败: {e}")

            return new_works_for_user

        for batch_start in range(0, len(user_ids), batch_size):
            batch = user_ids[batch_start:batch_start + batch_size]
            logger.info(f"处理用户批次 {batch_start + 1}-{batch_start + len(batch)}")

            batch_results = await asyncio.gather(*[check_user(uid) for uid in batch])
            for user_new_works in batch_results:
                if user_new_works:
                    new_works_total += len(user_new_works)
                    users_with_new_works += 1

            if batch_start + batch_size < len(user_ids):
                await asyncio.sleep(batch_size)

        logger.info("新作品检查完成")

        if shared.config.admin_user_id:
            summary = (
                f"📊 推送检查完成\n"
                f"总用户: {total_users}\n"
                f"新作品: {new_works_total}\n"
                f"有更新: {users_with_new_works} 人"
            )
            try:
                await context.bot.send_message(chat_id=shared.config.admin_user_id, text=summary)
            except Exception as e:
                logger.error(f"发送推送摘要失败: {e}")

    except Exception as e:
        logger.error(f"推送检查任务发生未预期异常: {e}", exc_info=True)


async def send_new_work_notification(bot: Bot, user_id: int, actress_name: str, work: dict[str, Any]) -> None:
    from . import _get_shared

    shared = _get_shared()
    try:
        av_id = work.get("id", "未知")
        av_date = work.get("date", "未知")
        av_title = work.get("title", "")
        img = work.get("img", "")

        lines = [
            "<b>🎉 关注女优更新啦！</b>",
            "",
            f"<b>👩 女优：</b>{html.escape(actress_name)}",
            f"<b>🎬 番号：</b><code>{html.escape(av_id)}</code>",
        ]
        if av_date != "未知":
            lines.append(f"<b>📅 日期：</b>{html.escape(av_date)}")
        if av_title:
            lines.append(f"<b>📝 标题：</b>{html.escape(av_title[:80])}")

        full_text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🧲 搜索 {av_id} 磁力", callback_data=_short_callback("magnet", av_id))],
            [InlineKeyboardButton(f"👩 查询 {actress_name}", callback_data=_short_callback("favquery", actress_name))]
        ])

        await send_photo_with_fallback(
            bot=bot, chat_id=user_id,
            img_url=img, caption=full_text,
            proxy_addr=shared.config.proxy_addr,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"发送新作品通知失败: {e}")


@require_auth
async def push_toggle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    user = update.effective_user
    favorites_manager = await get_favorites_manager()

    if not context.args:
        settings = await favorites_manager.get_push_settings(user.id)
        status = "✅ 已开启" if settings.get("push_enabled", True) else "❌ 已关闭"
        await msg.reply_text(
            f"📰 新作品推送状态：{status}\n\n"
            "使用 /push on 开启推送\n"
            "使用 /push off 关闭推送"
        )
        return

    action = context.args[0].lower()
    if action in ["on", "enable", "开启"]:
        await favorites_manager.set_push_enabled(user.id, True)
        await msg.reply_text("✅ 已开启新作品推送\n\n当你关注的女优有新作品时，我会及时通知你！")
    elif action in ["off", "disable", "关闭"]:
        await favorites_manager.set_push_enabled(user.id, False)
        await msg.reply_text("❌ 已关闭新作品推送")
    else:
        await msg.reply_text("用法：/push [on|off]")
