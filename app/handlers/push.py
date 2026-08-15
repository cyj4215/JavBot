from __future__ import annotations

import asyncio
import html
import logging
from typing import TYPE_CHECKING, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..fav import get_favorites_manager
from ..formatters.push import format_push_notification
from ..models import MergedWork
from ..secure_callback import short_callback as _short_callback
from .common import require_auth, require_auth_callback, send_photo_with_fallback

if TYPE_CHECKING:
    from telegram import Bot, Update

logger = logging.getLogger(__name__)

_MAX_CONCURRENT_QUERIES = 5
_PUSH_MODES = ("instant", "digest", "off")
_DIGEST_MAX_WORKS = 15
_digest_queue: dict[int, list[dict]] = {}


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
                settings = await favorites_manager.get_push_settings(user_id)
                mode = settings.get("push_mode", "instant")
            except Exception:
                mode = "instant"
            if mode == "off":
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
                        av_id = work.id
                        if not av_id:
                            continue
                        try:
                            is_new = await favorites_manager.record_user_work(
                                user_id=user_id,
                                actress_name=actress_name,
                                av_id=av_id,
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
                    if mode == "digest":
                        _digest_queue.setdefault(user_id, []).append(item)
                    else:
                        try:
                            await send_new_work_notification(
                                context.bot, user_id, item["actress_name"], item["work"]
                            )
                        except Exception as e:
                            logger.error(f"推送作品给用户 {user_id} 失败: {e}")

            try:
                await favorites_manager.update_last_check(user_id)
            except Exception as e:
                logger.error(f"更新用户 {user_id} 检查时间失败: {e}")

            return new_works_for_user

        for batch_start in range(0, len(user_ids), batch_size):
            batch = user_ids[batch_start : batch_start + batch_size]
            logger.info(f"处理用户批次 {batch_start + 1}-{batch_start + len(batch)}")

            batch_results = await asyncio.gather(*[check_user(uid) for uid in batch])
            for user_new_works in batch_results:
                if user_new_works:
                    new_works_total += len(user_new_works)
                    users_with_new_works += 1

            if batch_start + batch_size < len(user_ids):
                await asyncio.sleep(shared.config.push_batch_delay)

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


async def send_new_work_notification(
    bot: Bot, user_id: int, actress_name: str, work: MergedWork
) -> None:
    from . import _get_shared

    shared = _get_shared()
    lang = shared.service.i18n.DEFAULT_LANG
    try:
        fav_mgr = await get_favorites_manager()
        lang = await fav_mgr.get_user_language(user_id)
    except Exception:
        pass

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    try:
        caption, keyboard = format_push_notification(actress_name, work, _t=_)
        await send_photo_with_fallback(
            bot=bot,
            chat_id=user_id,
            img_url=work.img or "",
            caption=caption,
            proxy_addr=shared.config.proxy_addr,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error(f"发送新作品通知失败: {e}")


@require_auth
async def push_toggle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, msg, shared) -> None:
    from .common import make_t

    _ = await make_t(shared, update)
    user = update.effective_user
    favorites_manager = await get_favorites_manager()

    if not context.args:
        settings = await favorites_manager.get_push_settings(user.id)
        mode = settings.get("push_mode", "instant")
        status_text = {
            "instant": _("push_status", _("push_mode_instant_btn")),
            "digest": _("push_status", _("push_mode_digest_btn")),
            "off": _("push_status", _("push_mode_off_btn")),
        }.get(mode, _("push_status", _("push_mode_instant_btn")))
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        _("push_mode_instant_btn"), callback_data="pushmode:instant"
                    )
                ],
                [InlineKeyboardButton(_("push_mode_digest_btn"), callback_data="pushmode:digest")],
                [InlineKeyboardButton(_("push_mode_off_btn"), callback_data="pushmode:off")],
            ]
        )
        await msg.reply_text(status_text, reply_markup=keyboard)
        return

    action = context.args[0].lower()
    if action in ("on", "enable", "开启"):
        await favorites_manager.set_push_mode(user.id, "instant")
        await msg.reply_text(_("push_enabled_msg"))
    elif action in ("digest", "汇总"):
        await favorites_manager.set_push_mode(user.id, "digest")
        await msg.reply_text(_("push_digest_enabled_msg"))
    elif action in ("off", "disable", "关闭"):
        await favorites_manager.set_push_mode(user.id, "off")
        await msg.reply_text(_("push_disabled_msg"))
    else:
        await msg.reply_text(_("push_usage"))


@require_auth_callback
async def push_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, q, shared) -> None:
    from .common import make_t

    data = q.data or ""
    if not data.startswith("pushmode:"):
        await q.answer()
        return
    mode = data[len("pushmode:") :]
    if mode not in _PUSH_MODES:
        await q.answer()
        return

    _ = await make_t(shared, update)
    fav_mgr = await get_favorites_manager()
    await fav_mgr.set_push_mode(update.effective_user.id, mode)
    mode_label = _(
        "push_mode_instant_btn"
        if mode == "instant"
        else "push_mode_digest_btn"
        if mode == "digest"
        else "push_mode_off_btn"
    )
    await q.answer(_("push_mode_set", mode_label))
    await q.edit_message_text(_("push_mode_set", mode_label))


async def check_and_send_digests(context: ContextTypes.DEFAULT_TYPE) -> None:
    """定时把 digest 队列合并成汇总消息发送给各用户。"""
    from . import _get_shared

    shared = _get_shared()
    if not shared.config.push_enabled_global:
        return
    if not getattr(shared.config, "push_digest_enabled", True):
        dropped = sum(len(v) for v in _digest_queue.values())
        _digest_queue.clear()
        if dropped:
            logger.info("digest 全局关闭，丢弃积压 %d 条", dropped)
        return
    if not _digest_queue:
        return
    logger.info("发送 digest 汇总: %d 个用户", len(_digest_queue))
    for user_id, items in list(_digest_queue.items()):
        try:
            await send_digest_message(context.bot, user_id, items)
            _digest_queue.pop(user_id, None)
        except Exception as e:
            logger.error(f"发送 digest 给用户 {user_id} 失败: {e}")


async def send_digest_message(bot: Bot, user_id: int, items: list[dict]) -> None:
    from . import _get_shared

    shared = _get_shared()
    lang = shared.service.i18n.DEFAULT_LANG
    try:
        fav_mgr = await get_favorites_manager()
        lang = await fav_mgr.get_user_language(user_id)
    except Exception:
        pass

    def _(key, *a):
        return shared.service.i18n.t(key, lang, *a)

    by_actress: dict[str, list] = {}
    for item in items:
        by_actress.setdefault(item["actress_name"], []).append(item["work"])

    lines = [f"<b>{_('push_digest_title', min(len(items), _DIGEST_MAX_WORKS))}</b>", ""]
    keyboard_rows: list[list[InlineKeyboardButton]] = []
    displayed = 0
    hidden = 0
    for actress_name, works in by_actress.items():
        if displayed >= _DIGEST_MAX_WORKS:
            hidden += len(works)
            continue
        lines.append(f"<b>👩 {html.escape(actress_name)}</b>")
        for work in works[:3]:
            if displayed >= _DIGEST_MAX_WORKS:
                hidden += 1
                continue
            av_id = work.id or ""
            date = (work.date or "").strip()
            title = (work.title or "").strip()[:40]
            lines.append(
                f"🎬 <code>{html.escape(av_id)}</code>"
                + (f"  📅 {html.escape(date)}" if date else "")
                + (f"  📝 {html.escape(title)}" if title else "")
            )
            if av_id:
                keyboard_rows.append(
                    [
                        InlineKeyboardButton(
                            _("search_magnet_for", av_id),
                            callback_data=_short_callback("magnet", av_id),
                        )
                    ]
                )
            displayed += 1
        lines.append("")

    if hidden > 0:
        lines.append(_("push_digest_more", hidden))

    img_url = ""
    for item in items:
        if item["work"].img:
            img_url = item["work"].img
            break

    keyboard = InlineKeyboardMarkup(keyboard_rows) if keyboard_rows else None
    await send_photo_with_fallback(
        bot=bot,
        chat_id=user_id,
        img_url=img_url,
        caption="\n".join(lines),
        proxy_addr=shared.config.proxy_addr,
        reply_markup=keyboard,
    )
