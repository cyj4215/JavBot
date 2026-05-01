"""Playwright 浏览器连接池，用于绕过 Cloudflare 等反爬机制.

使用单例模式管理浏览器实例，避免重复启动开销.
通过强大的反检测措施模拟真实浏览器.
"""

from __future__ import annotations

import asyncio
import logging
import re
import atexit
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

_browser: Optional[Any] = None
_playwright: Optional[Any] = None
_lock = asyncio.Lock()


async def get_browser(headless: bool = True):
    """获取或启动共享浏览器实例."""
    global _browser, _playwright

    if _browser is not None:
        return _browser

    async with _lock:
        if _browser is not None:
            return _browser

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright 未安装")
            raise

        logger.info("启动 Playwright 浏览器...")
        _playwright = await async_playwright().start()

        # 使用 stealth 级别的反检测参数
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-infobars",
            "--disable-extensions",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu",
            "--window-size=1920,1080",
            "--start-maximized",
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]

        _browser = await _playwright.chromium.launch(
            headless=headless,
            args=args,
        )

        atexit.register(_cleanup_sync)
        logger.info("Playwright 浏览器启动完成")
        return _browser


def _cleanup_sync():
    if _browser is not None or _playwright is not None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_cleanup())
        except RuntimeError:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(_cleanup())
                loop.close()
            except Exception:
                logger.error("关闭浏览器失败 (fallback loop)", exc_info=True)
        except Exception:
            logger.error("关闭浏览器失败 (atexit)", exc_info=True)


async def _cleanup():
    global _browser, _playwright
    logger.info("关闭 Playwright 浏览器...")
    try:
        if _browser:
            await _browser.close()
            _browser = None
        if _playwright:
            await _playwright.stop()
            _playwright = None
    except Exception as e:
        logger.warning(f"关闭浏览器时出错: {e}")


_STEALTH_SCRIPT = """
// 隐藏 webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// 模拟 plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
        {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
        {name: 'Native Client', filename: 'internal-nacl-plugin'}
    ]
});

// 模拟 languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en']
});

// 模拟 chrome 对象
window.chrome = {
    runtime: {
        OnInstalledReason: {CHROME_UPDATE: 'chrome_update'},
        OnRestartRequiredReason: {APP_UPDATE: 'app_update'},
        PlatformArch: {ARM64: 'arm64'},
        PlatformNaclArch: {ARM64: 'arm64'},
        PlatformOs: {MAC: 'mac'},
        RequestUpdateCheckStatus: {NO_UPDATE: 'no_update'}
    }
};

// 隐藏 automation
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({state: Notification.permission}) :
        originalQuery(parameters)
);

// 覆盖 permissions
Object.defineProperty(navigator, 'permissions', {
    value: {
        query: async (params) => {
            if (params.name === 'notifications') {
                return {state: 'default'};
            }
            return originalQuery(params);
        }
    }
});

// 模拟 Notification
if (!window.Notification) {
    window.Notification = {
        permission: 'default',
        requestPermission: () => Promise.resolve('default')
    };
}
"""


async def fetch_page(url: str, wait_selector: str = "body", timeout: int = 30000) -> str:
    """使用浏览器抓取页面内容."""
    browser = await get_browser()
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    page = await context.new_page()

    try:
        # 注入反检测脚本
        await page.add_init_script(_STEALTH_SCRIPT)

        logger.debug(f"导航到: {url}")
        response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

        if response:
            logger.debug(f"页面状态码: {response.status}")

        title = await page.title()
        if "moment" in title.lower() or "cloudflare" in title.lower():
            logger.info("检测到 Cloudflare 挑战，等待解决...")
            try:
                await page.wait_for_function(
                    "() => !document.title.toLowerCase().includes('moment') && !document.title.toLowerCase().includes('cloudflare')",
                    timeout=15000,
                )
            except Exception:
                logger.warning("Cloudflare 挑战等待超时，继续处理")
            title = await page.title()
            logger.info(f"挑战后标题: {title}")

        try:
            await page.wait_for_selector(wait_selector, timeout=timeout)
        except Exception:
            pass

        content = await page.content()
        return content

    finally:
        await context.close()


async def get_new_works_from_javdb(star_name: str, limit: int = 8) -> List[Dict[str, Any]]:
    """通过 Playwright 从 JavDb 获取女优最新作品."""
    from urllib.parse import quote
    from bs4 import BeautifulSoup

    search_url = f"https://javdb.com/search?q={quote(star_name)}&f=actor"
    logger.info(f"通过 Playwright 搜索 JavDb: {star_name}")

    try:
        # 第一步：搜索演员
        html = await fetch_page(search_url, wait_selector=".actor-box, .movie-list", timeout=60000)
        soup = BeautifulSoup(html, "html.parser")

        # 检查是否还是 CF 页面
        title = soup.find("title")
        if title and ("moment" in title.text.lower() or "cloudflare" in title.text.lower()):
            logger.warning(f"Cloudflare 挑战未通过: {star_name}")
            return []

        # 获取演员页面链接
        actor_box = soup.find(class_="actor-box")
        if not actor_box:
            logger.warning(f"未找到演员框，尝试直接解析: {star_name}")
            return _parse_movie_list(soup, limit)

        a_tag = actor_box.find("a")
        if not a_tag or not a_tag.get("href"):
            logger.warning(f"未找到演员链接: {star_name}")
            return []

        href = a_tag["href"]
        actor_url = f"https://javdb.com{href}" if not href.startswith("http") else href
        logger.info(f"访问演员页面: {actor_url}")

        # 第二步：访问演员页面获取作品
        actor_html = await fetch_page(actor_url, wait_selector=".movie-list", timeout=60000)
        actor_soup = BeautifulSoup(actor_html, "html.parser")

        works = _parse_movie_list(actor_soup, limit)
        logger.info(f"从 JavDb 获取到 {len(works)} 个作品: {star_name}")
        return works

    except Exception as e:
        logger.error(f"Playwright 抓取 JavDb 失败: {e}")
        return []


async def get_actors_from_javdb(limit: int = 20, page: int = 1, timeout: int = 25000) -> List[Dict[str, Any]]:
    """通过 Playwright 从 JavDb 获取演员列表.

    JavDb 的演员页面 /actors 提供了按人气排序的女优列表。
    """
    from bs4 import BeautifulSoup

    actors: List[Dict[str, Any]] = []
    url = f"https://javdb.com/actors?page={page}"
    logger.info(f"通过 Playwright 获取 JavDb 演员列表: page={page}")

    try:
        html = await fetch_page(url, wait_selector=".actor-box", timeout=timeout)
        soup = BeautifulSoup(html, "html.parser")

        # 检查是否还是 CF 页面
        title = soup.find("title")
        if title and ("moment" in title.text.lower() or "cloudflare" in title.text.lower()):
            logger.warning("Cloudflare 挑战未通过: JavDb actors")
            return []

        actor_boxes = soup.find_all(class_="actor-box")
        logger.info(f"JavDb 演员页面解析到 {len(actor_boxes)} 个演员")

        for box in actor_boxes[:limit]:
            try:
                a_tag = box.find("a")
                if not a_tag:
                    continue

                name = ""
                strong = a_tag.find("strong")
                if strong:
                    name = strong.get_text(strip=True)
                if not name:
                    name = a_tag.get("title", "").strip()

                href = a_tag.get("href", "")
                actor_url = f"https://javdb.com{href}" if href and not href.startswith("http") else href

                img = ""
                img_tag = box.find("img")
                if img_tag:
                    img = img_tag.get("src", img_tag.get("data-src", ""))

                if name:
                    actors.append({
                        "id": "",
                        "name": name,
                        "image_url": img,
                        "thumb_url": img,
                        "url": actor_url,
                    })
            except Exception:
                continue

        logger.info(f"从 JavDb 获取到 {len(actors)} 个演员")
        return actors

    except Exception as e:
        logger.error(f"Playwright 抓取 JavDb 演员列表失败: {e}")
        return []


def _parse_javdb_search(html: str, star_name: str, limit: int) -> List[Dict[str, Any]]:
    """解析 JavDb 搜索结果 HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    works: List[Dict[str, Any]] = []

    # 检查是否还是 CF 页面
    title = soup.find("title")
    if title and ("moment" in title.text.lower() or "cloudflare" in title.text.lower()):
        logger.warning(f"Cloudflare 挑战未通过: {star_name}")
        return []

    # 尝试找到演员页面链接
    actor_link = None
    actor_box = soup.find(class_="actor-box")
    if actor_box:
        a_tag = actor_box.find("a")
        if a_tag and a_tag.get("href"):
            actor_link = a_tag["href"]
            if not actor_link.startswith("http"):
                actor_link = f"https://javdb.com{actor_link}"

    if not actor_link:
        logger.warning(f"未找到演员页面链接: {star_name}")
        return _parse_movie_list(soup, limit)

    return _parse_movie_list(soup, limit)


def _parse_movie_list(soup, limit: int) -> List[Dict[str, Any]]:
    """从 JavDb 页面解析作品列表."""
    works: List[Dict[str, Any]] = []

    movie_list = soup.find(class_="movie-list")
    if movie_list:
        items = movie_list.find_all("a", class_="box", limit=limit)
        for item in items:
            try:
                # 番号可能在 <strong> 标签内
                strong_tag = item.find("strong")
                av_id = strong_tag.text.strip() if strong_tag else ""

                # 或者 class="uid"
                if not av_id:
                    uid_tag = item.find(class_="uid")
                    av_id = uid_tag.text.strip() if uid_tag else ""

                # 标题
                title_tag = item.find(class_="video-title")
                title = ""
                if title_tag:
                    # 去掉番号部分
                    title_text = title_tag.get_text(strip=True)
                    title = title_text.replace(av_id, "").strip()

                # 日期
                meta_tag = item.find(class_="meta")
                date = ""
                if meta_tag:
                    date_text = meta_tag.text.strip()
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
                    if date_match:
                        date = date_match.group(1)

                # 封面图
                img_tag = item.find("img")
                img = img_tag.get("src", "") if img_tag else ""
                if not img:
                    img = img_tag.get("data-src", "") if img_tag else ""

                # URL
                url = item.get("href", "")
                if url and not url.startswith("http"):
                    url = f"https://javdb.com{url}"

                if av_id:
                    works.append({
                        "id": av_id,
                        "title": title,
                        "date": date or "未知",
                        "img": img,
                        "url": url,
                    })
            except Exception:
                continue

    return works
