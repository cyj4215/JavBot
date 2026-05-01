"""
改进的工具模块 - 为 jvav_bot 提供更好的错误处理和重试机制
"""

import logging
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 获取模块 logger
logger = logging.getLogger('jvav_bot.download')


def build_retry_session(proxy_addr: str = "") -> requests.Session:
    """构建带重试的 HTTP 会话"""
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if proxy_addr:
        session.proxies.update({"http": proxy_addr, "https": proxy_addr})
    return session


def download_image(url: str, proxy_addr: str = "", max_retries: int = 3) -> Optional[bytes]:
    """
    下载图片到内存，改进版：
    - 自动重试（默认3次）
    - 详细的错误日志
    - 超时保护
    - 状态码验证
    """
    if not url:
        logger.debug(f"图片URL为空，跳过下载")
        return None

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
                if attempt < max_retries - 1:
                    continue  # 继续重试
                else:
                    logger.error(f"下载失败（已达最大重试次数）：{url}")
                    return None
            
            if len(resp.content) < 1024:
                logger.warning(f"响应内容过小（第{attempt+1}次）：{len(resp.content)} bytes, URL: {url}")
                if attempt < max_retries - 1:
                    continue  # 继续重试
                else:
                    logger.error(f"响应内容过小（已达最大重试次数）：{url}")
                    return None
            
            # 成功下载
            logger.info(f"成功下载图片：{url}，大小：{len(resp.content)} bytes")
            return resp.content
            
        except requests.Timeout as e:
            logger.warning(f"下载超时（第{attempt+1}次）：{url}，超时：15秒")
            if attempt < max_retries - 1:
                continue  # 继续重试
            else:
                logger.error(f"下载超时（已达最大重试次数）：{url}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"下载请求失败（第{attempt+1}次）：{url}，错误：{e}")
            if attempt < max_retries - 1:
                continue  # 继续重试
            else:
                logger.error(f"下载请求失败（已达最大重试次数）：{url}")
                return None
                
        except Exception as e:
            logger.error(f"未知错误（第{attempt+1}次）：{url}，错误类型：{type(e).__name__}，错误：{e}")
            if attempt < max_retries - 1:
                continue  # 继续重试
            else:
                logger.error(f"未知错误（已达最大重试次数）：{url}")
                return None
    
    return None


# 统计信息
_download_stats = {
    "total_attempts": 0,
    "success": 0,
    "failures": 0,
    "timeouts": 0,
}


def get_download_stats() -> dict:
    """获取下载统计信息"""
    return _download_stats.copy()


def reset_download_stats() -> None:
    """重置下载统计"""
    global _download_stats
    _download_stats = {
        "total_attempts": 0,
        "success": 0,
        "failures": 0,
        "timeouts": 0,
    }
