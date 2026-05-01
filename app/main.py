import logging
from datetime import time as datetime_time

from dotenv import load_dotenv

from telegram import BotCommand, MenuButtonCommands
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import BotConfig
from .service import ActressService
from .handlers import _set_shared
from .handlers.common import start, help_cmd, menu_callback
from .handlers.search import search_cmd, on_text
from .handlers.magnet import magnet_cmd
from .handlers.rank import rank_cmd, rank_page_callback
from .handlers.favorites import (
    favorite_cmd,
    unfavorite_cmd,
    my_favorites_cmd,
    favorites_latest_cmd,
    favorite_query_callback,
)
from .handlers.push import check_and_push_new_works, push_toggle_cmd
from .favorites import get_favorites_manager
from .scheduler import scheduled_cleanup

load_dotenv()


async def post_init(application: Application) -> None:
    logging.info("开始执行post_init函数")
    logging.info("初始化收藏管理器")
    get_favorites_manager()
    logging.info("收藏管理器初始化完成")

    from .handlers import _get_shared
    shared = _get_shared()
    config = shared.config

    try:
        await shared.service.start_rank_background_refresh()
        logging.info("排行榜后台预热已启动")
    except Exception as e:
        logging.warning("排行榜后台预热启动失败: %s", e, exc_info=True)

    commands = [
        BotCommand("start", "开始使用"),
        BotCommand("help", "查看帮助"),
        BotCommand("s", "查询女优信息"),
        BotCommand("search", "搜索磁力链接"),
        BotCommand("rank", "查看热门女优榜"),
        BotCommand("fav", "收藏女优"),
        BotCommand("unfav", "取消收藏"),
        BotCommand("myfav", "我的收藏"),
        BotCommand("favlatest", "收藏女优最新作品"),
        BotCommand("push", "新作品推送开关"),
    ]
    try:
        logging.info("设置命令菜单")
        await application.bot.set_my_commands(commands)
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logging.info("命令菜单设置完成")

        admin_user_id = config.admin_user_id
        logging.info(f"Admin user ID: {admin_user_id}")
        if admin_user_id:
            try:
                logging.info(f"发送启动消息到用户: {admin_user_id}")
                await application.bot.send_message(
                    chat_id=admin_user_id,
                    text="🚀 机器人已成功启动！\n\n" +
                         "功能列表：\n" +
                         "• /s 名字 - 查询女优信息\n" +
                         "• /search 关键词 - 搜索磁力链接\n" +
                         "• /rank - 查看热门女优榜\n" +
                         "• /fav 名字 - 收藏女优\n" +
                         "• /unfav 名字 - 取消收藏\n" +
                         "• /myfav - 查看我的收藏\n" +
                         "• /favlatest - 查看收藏女优最新作品\n" +
                         "\n支持一次性添加/取消多个收藏，用逗号或分号分隔\n" +
                         "例如：/fav 三上悠亚, 苍井空; 波多野结衣\n\n" +
                         "点击 /start 开始使用！",
                    parse_mode=ParseMode.HTML
                )
                logging.info("启动消息发送成功")
            except Exception as e:
                logging.error(f"发送启动消息失败: {e}", exc_info=True)
        else:
            logging.warning("ADMIN_USER_ID环境变量未设置，跳过发送启动消息")
    except Exception as exc:
        logging.error("设置命令菜单失败: %s", exc, exc_info=True)
    logging.info("post_init函数执行完成")


def build_app() -> Application:
    config = BotConfig.from_env()

    service = ActressService(
        proxy_addr=config.proxy_addr,
        latest_limit=config.latest_limit,
        top_limit=config.top_limit,
        profile_cache_ttl=config.profile_cache_ttl,
        rank_cache_ttl=config.rank_cache_ttl,
        uncensored=config.uncensored,
    )

    _set_shared(config, service)

    app = Application.builder().token(config.token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("s", search_cmd))
    app.add_handler(CommandHandler("search", magnet_cmd))
    app.add_handler(CommandHandler("magnet", magnet_cmd))
    app.add_handler(CommandHandler("m", magnet_cmd))
    app.add_handler(CommandHandler("rank", rank_cmd))
    app.add_handler(CommandHandler("top", rank_cmd))
    app.add_handler(CommandHandler("fav", favorite_cmd))
    app.add_handler(CommandHandler("unfav", unfavorite_cmd))
    app.add_handler(CommandHandler("myfav", my_favorites_cmd))
    app.add_handler(CommandHandler("favlatest", favorites_latest_cmd))
    app.add_handler(CommandHandler("push", push_toggle_cmd))
    app.add_handler(CallbackQueryHandler(rank_page_callback, pattern=r"^rank"))
    app.add_handler(CallbackQueryHandler(favorite_query_callback, pattern=r"^(fav|myfav|unfav)"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:|^search:|^magnet:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if config.push_enabled_global:
        job_queue = app.job_queue
        job_queue.run_repeating(
            check_and_push_new_works,
            interval=config.push_check_interval,
            first=10
        )
        job_queue.run_daily(
            scheduled_cleanup,
            time=datetime_time(hour=3, minute=0)
        )
        logging.info("已启用新作品推送检查，间隔: %s秒", config.push_check_interval)

    return app


def main() -> None:
    config = BotConfig.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("jvav.utils").setLevel(logging.CRITICAL)

    app = build_app()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
