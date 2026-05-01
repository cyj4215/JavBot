import logging
from typing import Optional
import requests

from .http_utils import build_retry_session

logger = logging.getLogger('jvav_bot.download')


def download_image(url: str, proxy_addr: str = "", max_retries: int = 3, session: Optional[requests.Session] = None) -> Optional[bytes]:
    if not url:
        logger.debug("图片URL为空，跳过下载")
        return None

    if session is None:
        session = build_retry_session(proxy_addr=proxy_addr)
    headers = {
        "Referer": "https://www.javbus.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for attempt in range(max_retries):
        try:
            logger.debug(f"尝试下载图片 (第{attempt+1}次): {url}")
            resp = session.get(url, timeout=15, headers=headers)

            if resp.status_code != 200:
                logger.warning(f"下载失败（第{attempt+1}次）：状态码 {resp.status_code}, URL: {url}")
                if attempt == max_retries - 1:
                    logger.error(f"下载失败（已达最大重试次数）：{url}")
                    return None
                continue

            if len(resp.content) < 1024:
                logger.warning(f"响应内容过小（第{attempt+1}次）：{len(resp.content)} bytes, URL: {url}")
                if attempt == max_retries - 1:
                    logger.error(f"响应内容过小（已达最大重试次数）：{url}")
                    return None
                continue

            logger.info(f"成功下载图片：{url}，大小：{len(resp.content)} bytes")
            return resp.content

        except Exception as e:
            if isinstance(e, requests.Timeout):
                logger.warning(f"下载超时（第{attempt+1}次）：{url}，超时：15秒")
            elif isinstance(e, requests.RequestException):
                logger.error(f"下载请求失败（第{attempt+1}次）：{url}，错误：{e}")
            else:
                logger.error(f"未知错误（第{attempt+1}次）：{url}，错误类型：{type(e).__name__}，错误：{e}")

            if attempt == max_retries - 1:
                logger.error(f"下载失败（已达最大重试次数）：{url}")
                return None

    return None
