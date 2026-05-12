import logging

from telegram.ext import ContextTypes

from .fav_manager import get_favorites_manager

logger = logging.getLogger(__name__)


async def scheduled_cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        favorites_manager = await get_favorites_manager()
        logger.info("开始执行定时数据库清理...")
        await favorites_manager.cleanup_old_data(days=90)
        await favorites_manager.optimize_database()
        logger.info("定时数据库清理完成")
    except Exception as e:
        logger.error(f"定时清理失败: {e}", exc_info=True)
