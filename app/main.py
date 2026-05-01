import asyncio
import copy
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import html
import logging
import os
import re
from threading import RLock
import time
import unicodedata
from urllib.parse import unquote, urlparse
from dataclasses import dataclass
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from jvav import DmmUtil, JavBusUtil

from .magnet_search import search_magnets
from .favorites import get_favorites_manager
from .improved_utils import download_image
import requests
from requests.adapters import HTTPAdapter
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    MenuButtonCommands,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from urllib3.util.retry import Retry
from pypinyin import pinyin, Style
import wikipediaapi

try:
    from opencc import OpenCC
except Exception:  # pragma: no cover
    OpenCC = None


load_dotenv()


class TTLCache:
    def __init__(self, max_size: int = 1024, default_ttl: int = 600):
        self.max_size = max(64, max_size)
        self.default_ttl = max(30, default_ttl)
        self._lock = RLock()
        self._data: OrderedDict = OrderedDict()

    def get(self, key):
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expire_at, value = item
            if expire_at < now:
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return copy.deepcopy(value)

    def set(self, key, value, ttl: Optional[int] = None):
        expire_at = time.time() + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            if key in self._data:
                self._data.pop(key, None)
            self._data[key] = (expire_at, copy.deepcopy(value))
            while len(self._data) > self.max_size:
                self._data.popitem(last=False)


def build_retry_session(proxy_addr: str = "") -> requests.Session:
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


@dataclass
class ActressProfile:
    found: bool
    query: str
    star_name: Optional[str] = None
    star_id: Optional[str] = None
    wiki_title: Optional[str] = None
    wiki_url: Optional[str] = None
    latest_works: Optional[List[dict]] = None
    top_ids: Optional[List[str]] = None
    top_works: Optional[List[dict]] = None
    suggestions: Optional[List[str]] = None
    matched_name: Optional[str] = None
    extra_info: Optional[dict] = None


class ActressService:
    def __init__(
        self,
        proxy_addr: str = "",
        latest_limit: int = 5,
        top_limit: int = 5,
        profile_cache_ttl: int = 1800,
        rank_cache_ttl: int = 900,
        uncensored: bool = False
    ):
        self.latest_limit = latest_limit
        self.top_limit = top_limit
        self.proxy_addr = proxy_addr
        self.uncensored = uncensored
        # 开启jvav内置缓存，减少重复请求
        self.javbus = JavBusUtil(proxy_addr=proxy_addr, use_cache=True)
        self.dmm = DmmUtil(proxy_addr=proxy_addr, use_cache=True)
        self.s2t = OpenCC("s2t") if OpenCC else None
        self.t2s = OpenCC("t2s") if OpenCC else None
        self.wiki_user_agent = "tg-jvav-bot/1.0 (https://t.me/My_JavBot_bot)"
        self.http = build_retry_session(proxy_addr=proxy_addr)
        self.profile_cache = TTLCache(max_size=2048, default_ttl=profile_cache_ttl)
        self.rank_cache = TTLCache(max_size=256, default_ttl=rank_cache_ttl)
        self.av_meta_cache = TTLCache(max_size=4096, default_ttl=43200)
        self.wiki_page_cache = TTLCache(max_size=2048, default_ttl=3600)
        # 常见中文译名映射表，第一优先级
        self.alias_map = {
            "三上悠亚": "三上悠亜",
            "明日花绮罗": "明日花キララ",
            "波多野结衣": "はたの ゆい",
            "苍井空": "蒼井そら",
            "吉泽明步": "吉沢明歩",
            "麻生希": "麻生希",
            "天海翼": "天海つばさ",
            "深田咏美": "深田えいみ",
            "桥本有菜": "橋本ありな",
            "相泽南": "相沢みなみ",
            "桃乃木香奈": "桃乃木かな",
            "伊藤舞雪": "伊藤舞雪",
            "枫可怜": "楓カレン",
            "明里紬": "明里つむぎ",
            "高桥圣子": "高橋しょう子",
            "天使萌": "天使もえ",
            "葵司": "葵つかさ",
            "椎名空": "椎名そら",
            "凉森玲梦": "涼森れむ",
            "河北彩花": "河北彩花"
        }

    @staticmethod
    def _normalize_name(name: str) -> str:
        return unicodedata.normalize("NFKC", name).strip()

    @staticmethod
    def _contains_cjk(text: str) -> bool:
        return bool(re.search(r"[\u3400-\u9fff]", text))

    def _to_traditional(self, text: str) -> str:
        if not self.s2t:
            return text
        try:
            return self.s2t.convert(text)
        except Exception:
            return text

    def _to_simplified(self, text: str) -> str:
        if not self.t2s:
            return text
        try:
            return self.t2s.convert(text)
        except Exception:
            return text

    def _name_candidates(self, name: str) -> List[str]:
        seen = set()
        candidates: List[str] = []

        def add(v: str) -> None:
            vv = self._normalize_name(v)
            if vv and vv not in seen:
                seen.add(vv)
                candidates.append(vv)

        # 第一层：硬编码别名映射
        if name in self.alias_map:
            add(self.alias_map[name])

        # 第二层：原名字候选（简繁转换、去空格）
        add(name)
        no_space = name.replace(" ", "")
        add(no_space)

        if self._contains_cjk(name):
            add(self._to_traditional(name))
            add(self._to_simplified(name))
            add(self._to_traditional(no_space))
            add(self._to_simplified(no_space))

            # 第三层：拼音候选
            try:
                pinyin_full = " ".join([i[0] for i in pinyin(name, style=Style.NORMAL)])
                add(pinyin_full)
                pinyin_full_no_space = "".join([i[0] for i in pinyin(name, style=Style.NORMAL)])
                add(pinyin_full_no_space)
                pinyin_initials = "".join([i[0][0].lower() for i in pinyin(name, style=Style.NORMAL)])
                add(pinyin_initials)
            except Exception:
                pass
        return candidates







    def _find_star(self, candidates: List[str]) -> tuple[Optional[str], Optional[dict]]:
        # 先查DMM，对中文名匹配更好
        for cand in candidates:
            try:
                code, stars = self.dmm.search_star(cand)
                if code == 200 and stars and len(stars) > 0:
                    # 取第一个匹配结果
                    star = stars[0]
                    # 用DMM返回的名字去JavBus查完整信息
                    code, javbus_star = self.javbus.check_star_exists(star.get("name", cand))
                    if code == 200 and javbus_star:
                        return cand, javbus_star
            except Exception:
                pass
        # DMM没查到再查JavBus
        for cand in candidates:
            code, star = self.javbus.check_star_exists(cand)
            if code == 200 and star:
                return cand, star
        return None, None

    def _get_av_meta(self, av_id: str, is_uncensored: Optional[bool] = None) -> dict:
        """获取作品详情，支持有码/无码切换"""
        if is_uncensored is None:
            is_uncensored = self.uncensored
        cached = self.av_meta_cache.get((av_id, is_uncensored))
        if cached is not None:
            return cached
        meta = {
            "id": av_id,
            "date": "未知",
            "img": "",
            "url": "",
            "title": "",
            "magnets": []
        }
        try:
            code, av = self.javbus.get_av_by_id(av_id, is_nice=False, is_uncensored=is_uncensored)
            if code == 200 and isinstance(av, dict):
                date = (av.get("date") or "").strip()
                img = (av.get("img") or "").strip()
                url = (av.get("url") or "").strip()
                title = (av.get("title") or "").strip()
                if date:
                    meta["date"] = date
                if img.startswith("http://") or img.startswith("https://"):
                    meta["img"] = img
                if url:
                    meta["url"] = url
                if title:
                    meta["title"] = title
                # 直接获取JavBus的磁力链接
                code, magnets = self.javbus.get_av_magnets(av_id, is_uncensored=is_uncensored)
                if code == 200 and magnets:
                    meta["magnets"] = [{"title": m.get("title", ""), "size": m.get("size", ""), "magnet": m.get("magnet", "")} for m in magnets[:3]]
        except Exception:
            pass
        self.av_meta_cache.set((av_id, is_uncensored), meta)
        return meta

    def get_av_magnets(self, av_id: str, limit: int = 5) -> List[dict]:
        """双源获取磁力：JavBus + sukebei.nyaa.si"""
        javbus_magnets = []
        try:
            code, magnets = self.javbus.get_av_magnets(av_id, is_uncensored=self.uncensored)
            if code == 200 and magnets:
                javbus_magnets = [{"title": m.get("title", ""), "size": m.get("size", ""), "magnet": m.get("magnet", "")} for m in magnets[:limit]]
        except Exception:
            pass
        # 合并sukebei的搜索结果
        from .magnet_search import search_magnets
        sukebei_magnets = search_magnets(av_id, max(0, limit - len(javbus_magnets)), 20)
        # 去重
        seen = set()
        result = []
        for m in javbus_magnets + sukebei_magnets:
            magnet = m.get("magnet", "").strip()
            if not magnet or magnet in seen:
                continue
            seen.add(magnet)
            result.append(m)
            if len(result) >= limit:
                break
        return result

    def _build_latest_works(self, ids: List[str]) -> List[dict]:
        works: List[dict] = [{} for _ in ids]
        if not ids:
            return works
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(ids)))) as executor:
            future_map = {
                executor.submit(self._get_av_meta, av_id): idx
                for idx, av_id in enumerate(ids)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    works[idx] = future.result()
                except Exception:
                    works[idx] = {"id": ids[idx], "date": "未知", "img": "", "url": "", "title": ""}
        return works

    def _wiki_page_by_lang(self, topic: str, from_lang: str, to_lang: str) -> dict:
        """获取维基百科语言链接"""
        import logging
        logger = logging.getLogger(__name__)
        
        cache_key = ("wiki_page", topic, from_lang, to_lang)
        cached = self.wiki_page_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"从缓存获取wiki_page: {cache_key} -> {cached}")
            return cached
        
        logger.debug(f"开始查询维基百科: topic={topic}, from_lang={from_lang}, to_lang={to_lang}")
        try:
            wiki = wikipediaapi.Wikipedia(language=from_lang, user_agent=self.wiki_user_agent)
            page = wiki.page(topic)
            if not page or not page.exists():
                logger.debug(f"维基百科页面不存在: {topic}")
                self.wiki_page_cache.set(cache_key, {})
                return {}
            
            logger.debug(f"找到维基百科页面: {page.title}, URL: {page.fullurl}")
            langlinks = page.langlinks or {}
            if to_lang in langlinks:
                linked = langlinks[to_lang]
                result = {
                    "title": linked.title,
                    "url": linked.fullurl,
                    "lang": linked.language,
                }
                logger.debug(f"找到语言链接到 {to_lang}: {result}")
                self.wiki_page_cache.set(cache_key, result)
                return result
            
            result = {
                "title": page.title,
                "url": page.fullurl,
                "lang": from_lang,
            }
            logger.debug(f"使用原始页面: {result}")
            self.wiki_page_cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.debug(f"维基百科查询异常: {e}")
            self.wiki_page_cache.set(cache_key, {})
            return {}

    def _wiki_aliases(self, name: str) -> List[str]:
        """从维基百科获取别名（语言链接）"""
        aliases: List[str] = []
        seen = set()

        def add(v: str) -> None:
            vv = self._normalize_name(v)
            if vv and vv not in seen:
                seen.add(vv)
                aliases.append(vv)

        if self._contains_cjk(name):
            p = self._wiki_page_by_lang(name, from_lang="zh", to_lang="ja")
            add(p.get("title", ""))
            p = self._wiki_page_by_lang(name, from_lang="zh", to_lang="en")
            add(p.get("title", ""))
        else:
            p = self._wiki_page_by_lang(name, from_lang="en", to_lang="ja")
            add(p.get("title", ""))
        return aliases

    def _extract_wikidata_entity_id(self, wiki_url: str) -> str:
        try:
            parsed = urlparse(wiki_url)
            title = unquote(parsed.path.split("/wiki/")[1]).strip()
            api_url = f"{parsed.scheme}://{parsed.netloc}/w/api.php"
            resp = self.http.get(
                api_url,
                params={
                    "action": "query",
                    "prop": "pageprops",
                    "titles": title,
                    "redirects": "1",
                    "format": "json",
                },
                timeout=20,
                headers={"user-agent": self.wiki_user_agent},
            )
            if resp.status_code != 200:
                return ""
            pages = (resp.json().get("query") or {}).get("pages") or {}
            for page in pages.values():
                pageprops = page.get("pageprops") or {}
                qid = (pageprops.get("wikibase_item") or "").strip()
                if qid:
                    return qid
        except Exception:
            return ""
        return ""

    @staticmethod
    def _format_wikidata_time(raw: str) -> str:
        m = re.match(r"^[+-](\d{4})-(\d{2})-(\d{2})T", raw or "")
        if not m:
            return ""
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    @staticmethod
    def _clean_wiki_text(text: str) -> str:
        t = re.sub(r"\[[^\]]+\]", "", text or "")
        t = " ".join(t.split())
        return t.strip()

    def _extract_info_from_wikidata(self, wiki_url: str) -> dict:
        info = {"birth_date": "", "height": "", "measurements": "", "cup": "", "socials": []}
        qid = self._extract_wikidata_entity_id(wiki_url)
        if not qid:
            return info
        try:
            resp = self.http.get(
                f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",
                timeout=20,
                headers={"user-agent": self.wiki_user_agent},
            )
            if resp.status_code != 200:
                return info
            entity = (resp.json().get("entities") or {}).get(qid) or {}
            claims = entity.get("claims") or {}

            def claim_str(pid: str) -> str:
                items = claims.get(pid) or []
                for item in items:
                    dv = (((item or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value")
                    if isinstance(dv, str):
                        return dv.strip()
                return ""

            # Birth date
            for item in claims.get("P569") or []:
                dv = (((item or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
                birth = self._format_wikidata_time(dv.get("time", ""))
                if birth:
                    info["birth_date"] = birth
                    break

            # Height
            for item in claims.get("P2048") or []:
                dv = (((item or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
                amount_raw = dv.get("amount", "")
                unit = dv.get("unit", "")
                if not amount_raw:
                    continue
                try:
                    amount = abs(float(amount_raw))
                except Exception:
                    continue
                if unit.endswith("/Q11573"):  # metre
                    info["height"] = f"{round(amount * 100)} cm"
                else:
                    info["height"] = f"{amount:g}"
                break

            socials = []
            social_map = [
                ("P2002", "X/Twitter", "https://x.com/{v}"),
                ("P2003", "Instagram", "https://www.instagram.com/{v}"),
                ("P7085", "TikTok", "https://www.tiktok.com/@{v}"),
                ("P2397", "YouTube", "https://www.youtube.com/channel/{v}"),
                ("P856", "官网", "{v}"),
            ]
            for pid, label, url_tpl in social_map:
                raw = claim_str(pid)
                if not raw:
                    continue
                raw = raw.strip()
                if pid in ("P2002", "P2003", "P7085") and raw.startswith("@"):
                    raw = raw[1:]
                url = url_tpl.format(v=raw)
                socials.append({"label": label, "url": url})
            info["socials"] = socials
        except Exception:
            return info
        return info

    def _extract_info_from_wikipedia(self, wiki_url: str) -> dict:
        info = {"birth_date": "", "height": "", "measurements": "", "cup": "", "socials": []}
        try:
            resp = self.http.get(
                wiki_url,
                timeout=20,
                headers={"user-agent": self.wiki_user_agent},
            )
            if resp.status_code != 200:
                return info
            soup = self.javbus.get_soup(resp)
            infobox = soup.find("table", class_=lambda c: c and "infobox" in c.lower())
            if not infobox:
                return info

            def contains_any(label: str, keywords: List[str]) -> bool:
                return any(k in label for k in keywords)

            for row in infobox.find_all("tr"):
                th = row.find("th")
                td = row.find("td")
                if not th or not td:
                    continue
                label = self._clean_wiki_text(th.get_text(" ", strip=True))
                value = self._clean_wiki_text(td.get_text(" ", strip=True))
                if not value:
                    continue

                if contains_any(label, ["出生", "生年月日", "誕生日", "Born"]):
                    if not info["birth_date"]:
                        m = re.search(r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})", value)
                        info["birth_date"] = (
                            f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                            if m
                            else value
                        )
                elif contains_any(label, ["身高", "身長", "Height"]):
                    if not info["height"]:
                        v = value.split(" / ")[0].split("/")[0].strip()
                        info["height"] = v or value
                elif contains_any(label, ["三围", "スリーサイズ", "BWH", "Bust", "Waist", "Hip"]):
                    if not info["measurements"]:
                        info["measurements"] = value
                elif contains_any(label, ["罩杯", "カップ", "Cup"]):
                    if not info["cup"]:
                        info["cup"] = value

            socials = []
            for a in infobox.find_all("a", href=True):
                href = a.get("href", "").strip()
                if href.startswith("//"):
                    href = f"https:{href}"
                if not href.startswith("http"):
                    continue
                if any(
                    k in href.lower()
                    for k in ["x.com/", "twitter.com/", "instagram.com/", "tiktok.com/", "youtube.com/"]
                ):
                    if href not in [s["url"] for s in socials]:
                        label = "链接"
                        if "x.com" in href or "twitter.com" in href:
                            label = "X/Twitter"
                        elif "instagram.com" in href:
                            label = "Instagram"
                        elif "tiktok.com" in href:
                            label = "TikTok"
                        elif "youtube.com" in href:
                            label = "YouTube"
                        socials.append({"label": label, "url": href})
            info["socials"] = socials
        except Exception:
            return info
        return info

    def _get_star_extra_info(self, wiki_url: str) -> dict:
        import logging
        logger = logging.getLogger(__name__)
        
        info = {"birth_date": "", "height": "", "measurements": "", "cup": "", "socials": []}
        if not wiki_url:
            logger.debug(f"wiki_url为空，无法获取extra_info")
            return info
        
        logger.debug(f"开始获取extra_info，wiki_url: {wiki_url}")
        from_wiki = self._extract_info_from_wikipedia(wiki_url)
        from_wikidata = self._extract_info_from_wikidata(wiki_url)
        
        logger.debug(f"从Wikipedia获取的信息: {from_wiki}")
        logger.debug(f"从Wikidata获取的信息: {from_wikidata}")

        info["birth_date"] = from_wiki.get("birth_date") or from_wikidata.get("birth_date") or ""
        info["height"] = from_wiki.get("height") or from_wikidata.get("height") or ""
        info["measurements"] = from_wiki.get("measurements") or from_wikidata.get("measurements") or ""
        info["cup"] = from_wiki.get("cup") or from_wikidata.get("cup") or ""

        socials = []
        seen = set()
        for src in [from_wikidata.get("socials", []), from_wiki.get("socials", [])]:
            for s in src:
                url = (s.get("url") or "").strip()
                label = (s.get("label") or "链接").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                socials.append({"label": label, "url": url})
        info["socials"] = socials[:6]
        
        logger.debug(f"最终extra_info: {info}")
        return info

    def get_hot_star_rankings(self, limit: int = 20, page: int = 1) -> List[dict]:
        limit = max(1, min(limit, 50))
        page = max(1, min(page, 5))
        cache_key = ("rank", limit, page)
        cached = self.rank_cache.get(cache_key)
        if cached is not None:
            return cached
        
        # 添加重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                fetch_limit = min(100, max(page * limit, limit))
                # 直接使用jvav内置的DMM排行榜接口，无需自己维护GraphQL请求
                # 尝试使用不同的rank_type参数
                rank_types = ["actress", "dv actress", "fanza actress"]
                actresses = None
                
                for rank_type in rank_types:
                    try:
                        code, temp_actresses = self.dmm.get_rank(rank_type=rank_type, limit=fetch_limit)
                        if code == 200 and temp_actresses:
                            actresses = temp_actresses
                            break
                    except Exception as e:
                        logging.warning(f"尝试rank_type={rank_type}失败: {e}")
                        continue
                
                if not actresses:
                    if attempt < max_retries - 1:
                        time.sleep(1)  # 短暂延迟后重试
                        continue
                    # 尝试使用缓存的旧数据
                    return self.rank_cache.get(("rank", limit, 1)) or []
                
                result = []
                for idx, actress in enumerate(actresses, start=1):
                    name = (actress.get("name") or "").strip()
                    if name:
                        result.append(
                            {
                                "id": (actress.get("id") or "").strip(),
                                "name": name,
                                "image_url": (actress.get("img") or "").strip(),
                                "thumb_url": (actress.get("img") or "").strip(),
                            }
                        )
                start = (page - 1) * limit
                result = result[start : start + limit]
                self.rank_cache.set(cache_key, result)
                return result
            except Exception as e:
                logging.error(f"获取排行榜失败 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # 短暂延迟后重试
                    continue
                # 尝试使用缓存的旧数据
                return self.rank_cache.get(("rank", limit, 1)) or []

    def query_profile(self, name: str) -> ActressProfile:
        profile_cache_key = ("profile", self._normalize_name(name), self.latest_limit, self.top_limit)
        cached = self.profile_cache.get(profile_cache_key)
        if cached is not None:
            return ActressProfile(**cached)
        candidates = self._name_candidates(name)
        matched_name, star = self._find_star(candidates)

        if not star:
            for cand in list(candidates):
                for alias in self._wiki_aliases(cand):
                    if alias not in candidates:
                        candidates.append(alias)
            matched_name, star = self._find_star(candidates)

        if not star:
            suggestions: List[str] = []
            seen = set()
            for cand in candidates[:4]:
                code, names = self.javbus.fuzzy_search_stars(cand)
                if code != 200 or not names:
                    continue
                for n in names:
                    if n not in seen:
                        seen.add(n)
                        suggestions.append(n)
                    if len(suggestions) >= 10:
                        break
                if len(suggestions) >= 10:
                    break
            result = ActressProfile(
                found=False,
                query=name,
                suggestions=suggestions,
            )
            self.profile_cache.set(profile_cache_key, result.__dict__)
            return result

        star_name = star.get("star_name", name)
        star_id = star.get("star_id", "")

        def load_latest() -> List[dict]:
            code, ids = self.javbus.get_new_ids_by_star_name(star_name)
            if code == 200 and ids:
                return self._build_latest_works(ids[: self.latest_limit])
            return []

        def load_top_ids() -> List[str]:
            top: List[str] = []
            code, avs = self.dmm.get_nice_avs_by_star_name(star_name)
            if code == 200 and avs:
                seen_ids = set()
                for av in avs:
                    av_id = av.get("id")
                    if av_id and av_id not in seen_ids:
                        seen_ids.add(av_id)
                        top.append(av_id)
                    if len(top) >= self.top_limit:
                        break
            return top

        def load_wiki_extra() -> tuple[dict, dict]:
            wiki_page = self._wiki_page_by_lang(star_name, from_lang="ja", to_lang="zh")
            extra_info = self._get_star_extra_info(wiki_page.get("url", ""))
            return wiki_page, extra_info

        latest_works: List[dict] = []
        top_ids: List[str] = []
        wiki_page = {}
        extra_info = {}

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_latest = executor.submit(load_latest)
            future_top = executor.submit(load_top_ids)
            future_wiki = executor.submit(load_wiki_extra)

            try:
                latest_works = future_latest.result()
            except Exception:
                latest_works = []
            try:
                top_ids = future_top.result()
            except Exception:
                top_ids = []
            try:
                wiki_page, extra_info = future_wiki.result()
            except Exception:
                wiki_page, extra_info = {}, {}

        result = ActressProfile(
            found=True,
            query=name,
            star_name=star_name,
            star_id=star_id,
            wiki_title=wiki_page.get("title"),
            wiki_url=wiki_page.get("url"),
            latest_works=latest_works,
            top_ids=top_ids,
            matched_name=matched_name,
            extra_info=extra_info,
        )
        self.profile_cache.set(profile_cache_key, result.__dict__)
        return result


def format_profile(profile: ActressProfile, user_id: int = None) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """格式化女优信息，返回文本和内联键盘

    Args:
        profile: 女优信息
        user_id: 用户ID（用于检查收藏状态）

    Returns:
        Tuple[str, Optional[InlineKeyboardMarkup]]: (文本内容, 键盘布局)
    """
    if not profile.found:
        query = html.escape(profile.query)
        lines = [
            "<b>🔍 查询结果</b>",
            f"❌ 未找到：<code>{query}</code>",
        ]
        if profile.suggestions:
            lines.append("")
            lines.append("<b>💡 你可能想查：</b>")
            # 创建建议按钮
            keyboard = []
            row = []
            for idx, name in enumerate(profile.suggestions[:8], 1):
                row.append(InlineKeyboardButton(name, callback_data=f"search:{name}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            keyboard.append([InlineKeyboardButton("🔄 返回主菜单", callback_data="menu:search")])
            lines.append("")
            lines.append("点击下方按钮快速查询：")
            return "\n".join(lines), InlineKeyboardMarkup(keyboard)
        else:
            lines.append("")
            lines.append("💡 请尝试中文全名、日文名或英文名。")
            lines.append("")
            lines.append("用法：<code>/s 名字</code>")
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 返回主菜单", callback_data="menu:search")]
            ])
            return "\n".join(lines), keyboard

    star_name = html.escape(profile.star_name or "")
    star_id = html.escape(profile.star_id or "")
    lines = [
        f"<b>👩 女优信息</b>",
        f"<b>🎯 姓名：</b><code>{star_name}</code>",
        f"<b>🆔 演员ID：</b><code>{star_id}</code>",
    ]
    if profile.matched_name and profile.matched_name != profile.query:
        lines.append(f"<b>🔍 匹配关键词：</b>{html.escape(profile.matched_name)}")
    if profile.wiki_url:
        title = html.escape(profile.wiki_title or profile.star_name or "")
        wiki_url = html.escape(profile.wiki_url, quote=True)
        lines.append(f"<b>📚 Wiki：</b><a href=\"{wiki_url}\">{title}</a>")
    if profile.extra_info:
        birth_date = html.escape(profile.extra_info.get("birth_date", ""))
        height = html.escape(profile.extra_info.get("height", ""))
        measurements = html.escape(profile.extra_info.get("measurements", ""))
        cup = html.escape(profile.extra_info.get("cup", ""))
        socials = profile.extra_info.get("socials", [])
        if birth_date or height or measurements or cup or socials:
            lines.append("")
            lines.append("<b>📋 个人简介</b>")
            if birth_date:
                lines.append(f"• 🎂 出生日期：{birth_date}")
            if height:
                lines.append(f"• 📏 身高：{height}")
            if measurements:
                lines.append(f"• 👙 三围：{measurements}")
            if cup:
                lines.append(f"• 🚺 罩杯：{cup}")
            if socials:
                links = []
                for s in socials[:6]:
                    label = html.escape(s.get("label", "链接"))
                    url = html.escape(s.get("url", ""), quote=True)
                    if url:
                        links.append(f"<a href=\"{url}\">{label}</a>")
                if links:
                    lines.append("• 🌐 社媒：" + " | ".join(links))
    if profile.top_ids:
        lines.append("")
        lines.append("<b>🏆 高分作品</b>")
        lines.extend([f"• <code>{html.escape(i)}</code>" for i in profile.top_ids])

    lines.append("")
    lines.append("<i>🔧 数据来源：JavBus / DMM / Wikipedia（via jvav）</i>")
    lines.append(f"<i>⏰ 查询时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>")

    # 创建内联键盘（收藏/取消收藏按钮）
    keyboard = []
    if user_id is not None and profile.found:
        favorites_manager = get_favorites_manager()
        is_favorite = favorites_manager.is_favorite(user_id, profile.star_name)

        if is_favorite:
            # 已收藏，显示取消收藏按钮
            keyboard.append([
                InlineKeyboardButton("⭐ 已收藏", callback_data=f"unfavnow:{profile.star_name}"),
                InlineKeyboardButton("📰 查看最新作品", callback_data=f"favquery:{profile.star_name}")
            ])
        else:
            # 未收藏，显示收藏按钮
            keyboard.append([
                InlineKeyboardButton("☆ 收藏", callback_data=f"favnow:{profile.star_name}"),
                InlineKeyboardButton("📰 查看最新作品", callback_data=f"favquery:{profile.star_name}")
            ])
        
        # 添加磁力搜索按钮
        keyboard.append([
            InlineKeyboardButton("💾 搜索磁力", callback_data=f"magnet:{star_name}")
        ])
        
        # 添加返回主菜单按钮
        keyboard.append([
            InlineKeyboardButton("🏠 返回主菜单", callback_data="menu:search")
        ])

    return "\n".join(lines), InlineKeyboardMarkup(keyboard) if keyboard else None


def format_magnet_messages(query: str, items: List[dict], max_len: int = 3900) -> List[str]:
    q = html.escape(query)
    if not items:
        return [
            "<b>💾 磁力搜索</b>\n"
            f"🔍 关键词：<code>{q}</code>\n\n"
            "❌ 未找到结果。\n"
            "💡 试试：换关键词、用完整番号、或使用日文名。"
        ]

    messages: List[str] = []
    current_lines = ["<b>💾 磁力搜索</b>", f"🔍 关键词：<code>{q}</code>", ""]

    for idx, item in enumerate(items[:5], start=1):
        title = html.escape(item.get("title", ""))[:120]
        size = html.escape(item.get("size", "Unknown"))
        magnet = html.escape(item.get("magnet", ""))
        block_lines = [
            f"<b>🎯 {idx}. {title}</b>",
            f"📦 大小：<code>{size}</code>",
            f"🧲 磁力：<code>{magnet}</code>",
            "",
        ]

        candidate = "\n".join(current_lines + block_lines + ["<i>🔧 数据来源：sukebei.nyaa.si</i>"])
        if len(candidate) > max_len and len(current_lines) > 3:
            current_lines.append("<i>🔧 数据来源：sukebei.nyaa.si</i>")
            messages.append("\n".join(current_lines))
            current_lines = [
                "<b>💾 磁力搜索（续）</b>",
                f"🔍 关键词：<code>{q}</code>",
                "",
            ] + block_lines
        else:
            current_lines.extend(block_lines)

    current_lines.append("<i>🔧 数据来源：sukebei.nyaa.si</i>")
    current_lines.append(f"<i>⏰ 查询时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>")
    messages.append("\n".join(current_lines))
    return messages


def looks_like_av_id(text: str) -> bool:
    q = text.strip().upper()
    return bool(re.search(r"\b[A-Z]{2,8}[-_ ]?\d{2,6}\b", q))


def format_rankings(stars: List[dict], page: int) -> str:
    if not stars:
        return (
            "<b>🏆 热门女优排行榜</b>\n"
            "📊 来源：DMM 官方月榜\n\n"
            "❌ 暂时无法获取榜单，请稍后再试。"
        )

    lines = [
        "<b>🏆 热门女优排行榜</b>",
        f"📊 来源：DMM 官方月榜（第{page}页）",
        "",
        "<b>🌟 排名列表：</b>",
    ]
    for idx, star in enumerate(stars, start=1):
        name = html.escape(star.get("name", ""))
        if idx <= 3:
            # 前三名添加特殊标记
            medals = ["🥇", "🥈", "🥉"]
            lines.append(f"{medals[idx-1]} {idx}. {name}")
        else:
            lines.append(f"⭐ {idx}. {name}")
    lines.append("")
    lines.append(f"<i>⏰ 抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>")
    lines.append("<i>🔧 数据来源：DMM 官方月榜</i>")
    return "\n".join(lines)


def build_rank_keyboard(limit: int, page: int) -> InlineKeyboardMarkup:
    page = max(1, min(page, 5))
    limit = max(1, min(limit, 50))
    rows = []
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"rank:{limit}:{page - 1}:0"))
    if page < 5:
        nav.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"rank:{limit}:{page + 1}:0"))
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton("🖼️ 查看本页头像", callback_data=f"rank:{limit}:{page}:1"),
        ]
    )
    return InlineKeyboardMarkup(rows)

def build_app() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    proxy_addr = os.getenv("HTTP_PROXY", "").strip()
    latest_limit = int(os.getenv("LATEST_LIMIT", "5"))
    top_limit = int(os.getenv("TOP_LIMIT", "5"))
    send_latest_covers = os.getenv("SEND_LATEST_COVERS", "1").strip() not in ("0", "false", "False")
    latest_cover_limit = int(os.getenv("LATEST_COVER_LIMIT", "3"))
    magnet_limit = int(os.getenv("MAGNET_LIMIT", "5"))
    magnet_timeout = int(os.getenv("MAGNET_TIMEOUT", "20"))
    rank_limit_default = int(os.getenv("RANK_LIMIT", "20"))
    rank_page_default = int(os.getenv("RANK_PAGE", "1"))
    rank_feature_avatars = os.getenv("SEND_RANK_AVATARS", "1").strip() not in ("0", "false", "False")
    rank_avatar_limit = int(os.getenv("RANK_AVATAR_LIMIT", "20"))
    profile_cache_ttl = int(os.getenv("PROFILE_CACHE_TTL", "1800"))
    rank_cache_ttl = int(os.getenv("RANK_CACHE_TTL", "900"))
    uncensored = os.getenv("UNCENSORED", "0").strip() not in ("0", "false", "False")
    allowed_user_ids = {
        int(v.strip())
        for v in os.getenv("ALLOWED_USER_IDS", "").split(",")
        if v.strip().isdigit()
    }
    push_check_interval = int(os.getenv("PUSH_CHECK_INTERVAL", "3600"))  # 默认1小时检查一次
    push_enabled_global = os.getenv("PUSH_ENABLED", "1").strip() not in ("0", "false", "False")

    service = ActressService(
        proxy_addr=proxy_addr,
        latest_limit=latest_limit,
        top_limit=top_limit,
        profile_cache_ttl=profile_cache_ttl,
        rank_cache_ttl=rank_cache_ttl,
        uncensored=uncensored
    )

    def is_allowed(update: Update) -> bool:
        if not allowed_user_ids:
            return True
        user = update.effective_user
        if not user:
            return False
        return user.id in allowed_user_ids

    async def run_search_reply(msg, query: str, user_id: int = None) -> None:
        waiting = await msg.reply_text("查询中，请稍等...")
        try:
            profile = await asyncio.to_thread(service.query_profile, query)
            base_text, keyboard = format_profile(profile, user_id)

            await waiting.delete()
            
            await msg.reply_text(
                base_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )

            if send_latest_covers and profile.found and profile.latest_works:
                for work in profile.latest_works[:latest_cover_limit]:
                    if not work.get("id"):
                        continue
                        
                    img = (work.get("img") or "").strip()
                    av_id = (work.get("id") or "").strip()
                    av_date = (work.get("date") or "未知").strip()
                    av_title = (work.get("title") or "").strip()[:80]

                    work_lines = [
                        f"<b>🎬 {html.escape(av_id)}</b>"
                    ]
                    if av_date != "未知":
                        work_lines.append(f"� 出品时间：{html.escape(av_date)}")
                    if av_title:
                        work_lines.append(f"📝 {html.escape(av_title)}")
                    
                    work_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"🧲 搜索 {av_id} 磁力", callback_data=f"magnet:{av_id}")]
                    ])
                    
                    work_caption = "\n".join(work_lines)
                    
                    if img:
                        try:
                            img_bytes = await asyncio.to_thread(download_image, img, proxy_addr)
                            if img_bytes:
                                await msg.reply_photo(
                                    photo=img_bytes,
                                    caption=work_caption,
                                    parse_mode=ParseMode.HTML,
                                    reply_markup=work_keyboard,
                                )
                            else:
                                await msg.reply_photo(
                                    photo=img,
                                    caption=work_caption,
                                    parse_mode=ParseMode.HTML,
                                    reply_markup=work_keyboard,
                                )
                        except Exception as e:
                            logging.warning(f"发送封面图失败: {e}")
                            await msg.reply_text(
                                work_caption,
                                parse_mode=ParseMode.HTML,
                                disable_web_page_preview=True,
                                reply_markup=work_keyboard,
                            )
        except Exception as exc:
            logging.exception("query failed: %s", exc)
            await waiting.edit_text("查询失败，请稍后再试。")

    async def run_magnet_reply(msg, query: str) -> None:
        waiting = await msg.reply_text("正在查询，请稍等...")
        try:
            # 先查询番号详情
            av_meta = await asyncio.to_thread(service._get_av_meta, query)
            # 再获取双源磁力
            items = await asyncio.to_thread(
                service.get_av_magnets,
                query,
                magnet_limit,
            )
            # 拼接番号详情
            if av_meta.get("title"):
                detail_lines = ["<b>🎬 作品详情</b>"]
                detail_lines.append(f"<b>番号：</b><code>{html.escape(av_meta['id'])}</code>")
                detail_lines.append(f"<b>标题：</b>{html.escape(av_meta['title'])}")
                if av_meta.get("date") != "未知":
                    detail_lines.append(f"<b>日期：</b>{html.escape(av_meta['date'])}")
                if av_meta.get("img"):
                    try:
                        img_bytes = await asyncio.to_thread(download_image, av_meta["img"], proxy_addr)
                        if img_bytes:
                            await waiting.delete()
                            await msg.reply_photo(
                                photo=img_bytes,
                                caption="\n".join(detail_lines),
                                parse_mode=ParseMode.HTML
                            )
                        else:
                            await waiting.edit_text(
                                "\n".join(detail_lines),
                                parse_mode=ParseMode.HTML,
                                disable_web_page_preview=True,
                            )
                    except Exception:
                        await waiting.edit_text(
                            "\n".join(detail_lines),
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                        )
                else:
                    await waiting.edit_text(
                        "\n".join(detail_lines),
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
            else:
                await waiting.edit_text("正在搜索磁力，请稍等...")
            # 发送磁力结果
            messages = format_magnet_messages(query, items)
            for m in messages:
                await msg.reply_text(
                    m,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
        except Exception as exc:
            logging.exception("magnet search failed: %s", exc)
            await waiting.edit_text("搜索失败，请稍后再试。")

    async def send_rank_avatars_for_page(msg, stars: List[dict], page: int, limit: int) -> None:
        if not rank_feature_avatars:
            return
        sent = 0
        for idx, star in enumerate(stars, start=1):
            if sent >= max(1, rank_avatar_limit):
                break
            img = (star.get("thumb_url") or star.get("image_url") or "").strip()
            if not img:
                continue
            name = html.escape(star.get("name", "未知"))
            rank_no = (page - 1) * max(1, min(limit, 50)) + idx
            caption = f"<b>#{rank_no} {name}</b>"
            try:
                # 先下载头像到内存再发送，避免Telegram拉取外链失败
                img_bytes = await asyncio.to_thread(download_image, img, proxy_addr)
                if img_bytes:
                    await msg.reply_photo(
                        photo=img_bytes,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                    )
                    sent += 1
                else:
                    # 下载失败的话 fallback 到直接发链接
                    await msg.reply_photo(
                        photo=img,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                    )
                    sent += 1
            except Exception:
                continue

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not is_allowed(update):
            await update.effective_message.reply_text("无权限使用此机器人。")
            return
        text = (
            "🎉 欢迎使用女优信息查询机器人！\n\n"
            "你可以通过以下方式与我交互：\n"
            "• 直接发送女优名字查询信息\n"
            "• 发送番号自动搜索磁力链接\n"
            "• 使用下方按钮快速访问功能\n"
        )
        # 创建主菜单键盘
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔍 搜索女优", callback_data="menu:search"),
                InlineKeyboardButton("💾 磁力搜索", callback_data="menu:magnet")
            ],
            [
                InlineKeyboardButton("🏆 热门女优榜", callback_data="menu:rank"),
                InlineKeyboardButton("⭐ 我的收藏", callback_data="menu:favorites")
            ],
            [
                InlineKeyboardButton("ℹ️ 帮助信息", callback_data="menu:help")
            ]
        ])
        await update.effective_message.reply_text(text, reply_markup=keyboard)

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not is_allowed(update):
            await update.effective_message.reply_text("无权限使用此机器人。")
            return
        await update.effective_message.reply_text(
            "可用命令：\n"
            "/s 名字 - 查询女优信息\n\n"
            "/search 关键词 - 搜索磁力\n"
            "/magnet 关键词 - 搜索磁力\n"
            "/m 关键词 - 搜索磁力\n\n"
            "/rank [数量] [页码] - 热门女优排行榜（DMM）\n"
            "示例：/rank 20 1\n\n"
            "收藏功能：\n"
            "/fav 名字 - 收藏女优\n"
            "/unfav 名字 - 取消收藏\n"
            "/myfav - 查看我的收藏\n"
            "/favlatest - 查看收藏女优的最新作品\n\n"
            "也支持直接发送名字查询。\n"
            "提示：直接发送「番号样式文本」会自动做磁力搜索。\n\n"
            "提示：/rank 返回后可点击「查看本页头像」。\n\n"
            "可选环境变量：HTTP_PROXY、LATEST_LIMIT、TOP_LIMIT、SEND_LATEST_COVERS、LATEST_COVER_LIMIT、MAGNET_LIMIT、MAGNET_TIMEOUT、RANK_LIMIT、RANK_PAGE、SEND_RANK_AVATARS、RANK_AVATAR_LIMIT、PROFILE_CACHE_TTL、RANK_CACHE_TTL、ALLOWED_USER_IDS、UNCENSORED（是否查询无码内容，默认0）"
        )

    async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if not msg:
            return
        if not is_allowed(update):
            await msg.reply_text("无权限使用此机器人。")
            return

        query = " ".join(context.args).strip()
        if not query:
            await msg.reply_text("用法：/s 名字\n例如：/s 三上悠亚")
            return
        user = update.effective_user
        await run_search_reply(msg, query, user.id if user else None)

    async def magnet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if not msg:
            return
        if not is_allowed(update):
            await msg.reply_text("无权限使用此机器人。")
            return

        query = " ".join(context.args).strip()
        if not query:
            await msg.reply_text("用法：/search 关键词\n例如：/search SSIS-123")
            return
        await run_magnet_reply(msg, query)

    async def rank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if not msg:
            return
        if not is_allowed(update):
            await msg.reply_text("无权限使用此机器人。")
            return

        limit = rank_limit_default
        page = rank_page_default
        if len(context.args) >= 1 and context.args[0].isdigit():
            limit = int(context.args[0])
        if len(context.args) >= 2 and context.args[1].isdigit():
            page = int(context.args[1])

        waiting = await msg.reply_text("正在获取热门女优排行榜...")
        try:
            stars = await asyncio.to_thread(service.get_hot_star_rankings, limit, page)
            if not stars:
                # 尝试使用缓存数据
                cached_stars = service.rank_cache.get(("rank", limit, page))
                if cached_stars:
                    await waiting.edit_text(
                        f"<b>热门女优排行榜</b>\n" +
                        f"来源：DMM 官方月榜（第{page}页）\n" +
                        f"⚠️ 最新数据获取失败，显示缓存数据\n\n" +
                        format_rankings(cached_stars, page),
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=build_rank_keyboard(limit, page),
                    )
                else:
                    await waiting.edit_text(
                        "<b>热门女优排行榜</b>\n" +
                        "来源：DMM 官方月榜\n\n" +
                        "暂时无法获取榜单，请稍后再试。\n" +
                        "点击下方按钮重试：",
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 重试", callback_data=f"rank_retry:{limit}:{page}")]
                        ])
                    )
            else:
                await waiting.edit_text(
                    format_rankings(stars, page),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=build_rank_keyboard(limit, page),
                )
        except Exception as exc:
            logging.exception("rank fetch failed: %s", exc)
            await waiting.edit_text(
                "<b>热门女优排行榜</b>\n" +
                "来源：DMM 官方月榜\n\n" +
                "获取榜单失败，请稍后再试。\n" +
                "点击下方按钮重试：",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 重试", callback_data=f"rank_retry:{limit}:{page}")]
                ])
            )

    async def favorite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """收藏女优命令"""
        logger = logging.getLogger(__name__)
        msg = update.effective_message
        if not msg:
            return
        if not is_allowed(update):
            await msg.reply_text("无权限使用此机器人。")
            return

        query = " ".join(context.args).strip()
        if not query:
            await msg.reply_text("用法：/fav 女优名字\n例如：/fav 三上悠亚\n支持一次性添加多个女优，用逗号或分号分隔\n例如：/fav 三上悠亚, 苍井空; 波多野结衣")
            return

        # 分割多个女优名字
        actress_names = []
        logger.info(f"原始查询字符串: {query}")
        # 使用正则表达式分割，支持逗号、分号等分隔符
        names = re.split(r'[,;，；]+', query)
        logger.info(f"分割后的名字列表: {names}")
        for name in names:
            name = name.strip()
            logger.info(f"处理后的女优名字: '{name}'")
            if name:
                actress_names.append(name)
        logger.info(f"最终的女优名字列表: {actress_names}")
        logger.info(f"女优名字数量: {len(actress_names)}")

        if not actress_names:
            await msg.reply_text("未找到有效的女优名字")
            return

        user = update.effective_user
        favorites_manager = get_favorites_manager()

        results = []
        # 先查询女优信息
        waiting = await msg.reply_text(f"正在查询 {len(actress_names)} 位女优...")
        try:
            for actress_name in actress_names:
                profile = await asyncio.to_thread(service.query_profile, actress_name)
                if not profile.found:
                    results.append(f"❌ 未找到女优: {actress_name}")
                    continue

                # 添加收藏
                success = favorites_manager.add_favorite(
                    user_id=user.id,
                    actress_name=profile.star_name,
                    actress_id=profile.star_id,
                    actress_data={
                        'star_name': profile.star_name,
                        'star_id': profile.star_id,
                        'wiki_url': profile.wiki_url,
                        'extra_info': profile.extra_info
                    }
                )

                if success:
                    results.append(f"✅ 已收藏: {profile.star_name}")
                else:
                    results.append(f"❌ 收藏失败: {profile.star_name}")

        except Exception as exc:
            logging.exception("收藏失败: %s", exc)
            results.append(f"❌ 收藏失败: {str(exc)}")

        # 编辑等待消息，显示所有结果
        await waiting.edit_text("\n".join(results) + "\n\n使用 /myfav 查看所有收藏\n使用 /favlatest 查看收藏女优的最新作品")

    async def unfavorite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """取消收藏命令"""
        logger = logging.getLogger(__name__)
        msg = update.effective_message
        if not msg:
            return
        if not is_allowed(update):
            await msg.reply_text("无权限使用此机器人。")
            return

        query = " ".join(context.args).strip()
        if not query:
            await msg.reply_text("用法：/unfav 女优名字\n例如：/unfav 三上悠亚\n支持一次性取消多个收藏，用逗号或分号分隔\n例如：/unfav 三上悠亚, 苍井空; 波多野结衣")
            return

        # 分割多个女优名字
        actress_names = []
        logger.info(f"原始查询字符串: {query}")
        # 使用正则表达式分割，支持逗号、分号等分隔符
        names = re.split(r'[,;，；]+', query)
        logger.info(f"分割后的名字列表: {names}")
        for name in names:
            name = name.strip()
            logger.info(f"处理后的女优名字: '{name}'")
            if name:
                actress_names.append(name)
        logger.info(f"最终的女优名字列表: {actress_names}")
        logger.info(f"女优名字数量: {len(actress_names)}")

        if not actress_names:
            await msg.reply_text("未找到有效的女优名字")
            return

        user = update.effective_user
        favorites_manager = get_favorites_manager()

        results = []
        # 先查询女优信息
        waiting = await msg.reply_text(f"正在取消收藏 {len(actress_names)} 位女优...")
        try:
            for actress_name in actress_names:
                # 先检查是否已收藏
                if not favorites_manager.is_favorite(user.id, actress_name):
                    # 尝试匹配收藏中的名字
                    favorites = favorites_manager.get_favorites(user.id)
                    matched = None
                    for fav in favorites:
                        if actress_name.lower() in fav['actress_name'].lower() or fav['actress_name'].lower() in actress_name.lower():
                            matched = fav['actress_name']
                            break

                    if matched:
                        actress_name = matched
                    else:
                        results.append(f"❌ 未找到收藏: {actress_name}")
                        continue

                # 移除收藏
                success = favorites_manager.remove_favorite(user.id, actress_name)

                if success:
                    results.append(f"✅ 已取消收藏: {actress_name}")
                else:
                    results.append(f"❌ 取消收藏失败: {actress_name}")

        except Exception as exc:
            logging.exception("取消收藏失败: %s", exc)
            results.append(f"❌ 取消收藏失败: {str(exc)}")

        # 编辑等待消息，显示所有结果
        await waiting.edit_text("\n".join(results) + "\n\n使用 /myfav 查看所有收藏")

    async def my_favorites_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> None:
        """查看我的收藏命令"""
        msg = update.effective_message
        if not msg:
            return
        if not is_allowed(update):
            await msg.reply_text("无权限使用此机器人。")
            return

        user = update.effective_user
        favorites_manager = get_favorites_manager()

        favorites_per_page = 10
        favorites = favorites_manager.get_favorites(user.id, limit=100)  # 获取所有收藏

        if not favorites:
            await msg.reply_text(
                "你还没有收藏任何女优。\n\n"
                "使用 /fav 女优名字 来收藏女优\n"
                "例如：/fav 三上悠亚"
            )
            return

        total_favorites = len(favorites)
        total_pages = (total_favorites + favorites_per_page - 1) // favorites_per_page
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * favorites_per_page
        end_idx = start_idx + favorites_per_page
        page_favorites = favorites[start_idx:end_idx]

        # 构建收藏列表
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

        # 创建内联键盘，每个收藏一个按钮
        keyboard = []
        row = []
        for idx, fav in enumerate(page_favorites, start_idx + 1):
            actress_name = fav['actress_name']
            # 截断过长的名字
            display_name = actress_name[:15] + "..." if len(actress_name) > 15 else actress_name
            row.append(InlineKeyboardButton(
                f"{idx}. {display_name}",
                callback_data=f"favquery:{actress_name}"
            ))
            if len(row) == 2:  # 每行2个按钮
                keyboard.append(row)
                row = []

        if row:  # 添加最后一行
            keyboard.append(row)

        # 添加分页按钮
        if total_pages > 1:
            page_buttons = []
            if page > 1:
                page_buttons.append(InlineKeyboardButton("◀️ 上一页", callback_data=f"myfav:page:{page-1}"))
            if page < total_pages:
                page_buttons.append(InlineKeyboardButton("下一页 ▶️", callback_data=f"myfav:page:{page+1}"))
            if page_buttons:
                keyboard.append(page_buttons)

        # 添加查看最新作品按钮
        keyboard.append([InlineKeyboardButton("📰 查看所有收藏的最新作品", callback_data="favlatest:all")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await msg.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

    async def favorites_latest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """查看收藏女优的最新作品命令"""
        msg = update.effective_message
        if not msg:
            return
        if not is_allowed(update):
            await msg.reply_text("无权限使用此机器人。")
            return

        user = update.effective_user
        favorites_manager = get_favorites_manager()

        favorites = favorites_manager.get_favorites(user.id, limit=10)  # 限制最多10个

        if not favorites:
            await msg.reply_text(
                "你还没有收藏任何女优。\n\n"
                "使用 /fav 女优名字 来收藏女优\n"
                "例如：/fav 三上悠亚"
            )
            return

        waiting = await msg.reply_text(f"正在查询 {len(favorites)} 位收藏女优的最新作品...")

        try:
            all_latest_works = []

            # 并发查询所有收藏女优的最新作品
            async def query_actress_latest(fav):
                try:
                    profile = await asyncio.to_thread(service.query_profile, fav['actress_name'])
                    if profile.found and profile.latest_works:
                        for work in profile.latest_works[:2]:  # 每个女优取最新2部作品
                            work['actress_name'] = fav['actress_name']
                            all_latest_works.append(work)
                except Exception:
                    pass

            # 并发查询
            tasks = [query_actress_latest(fav) for fav in favorites]
            await asyncio.gather(*tasks)

            # 按日期排序
            all_latest_works.sort(key=lambda x: x.get('date', ''), reverse=True)

            if not all_latest_works:
                await waiting.edit_text("暂无最新作品信息。")
                return

            # 发送结果
            await waiting.delete()

            # 分批发送，避免消息过长
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

    async def favorite_query_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """收藏查询回调处理"""
        q = update.callback_query
        if not q or not q.message:
            return
        if not is_allowed(update):
            await q.answer("无权限使用", show_alert=True)
            return

        data = q.data or ""

        if data.startswith("myfav:page:"):
            # 分页查看我的收藏
            logging.info(f"收到分页回调: {data}")
            page = int(data[len("myfav:page:"):])
            await q.answer()
            # 获取用户和收藏管理器
            user = update.effective_user
            favorites_manager = get_favorites_manager()

            favorites_per_page = 10
            favorites = favorites_manager.get_favorites(user.id, limit=100)

            if not favorites:
                await q.edit_message_text(
                    "你还没有收藏任何女优。\n\n"
                    "使用 /fav 女优名字 来收藏女优\n"
                    "例如：/fav 三上悠亚"
                )
                return

            total_favorites = len(favorites)
            total_pages = (total_favorites + favorites_per_page - 1) // favorites_per_page
            page = max(1, min(page, total_pages))

            start_idx = (page - 1) * favorites_per_page
            end_idx = start_idx + favorites_per_page
            page_favorites = favorites[start_idx:end_idx]

            # 构建收藏列表
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

            # 创建内联键盘，每个收藏一个按钮
            keyboard = []
            row = []
            for idx, fav in enumerate(page_favorites, start_idx + 1):
                actress_name = fav['actress_name']
                # 截断过长的名字
                display_name = actress_name[:15] + "..." if len(actress_name) > 15 else actress_name
                row.append(InlineKeyboardButton(
                    f"{idx}. {display_name}",
                    callback_data=f"favquery:{actress_name}"
                ))
                if len(row) == 2:  # 每行2个按钮
                    keyboard.append(row)
                    row = []

            if row:  # 添加最后一行
                keyboard.append(row)

            # 添加分页按钮
            if total_pages > 1:
                page_buttons = []
                if page > 1:
                    page_buttons.append(InlineKeyboardButton("◀️ 上一页", callback_data=f"myfav:page:{page-1}"))
                if page < total_pages:
                    page_buttons.append(InlineKeyboardButton("下一页 ▶️", callback_data=f"myfav:page:{page+1}"))
                if page_buttons:
                    keyboard.append(page_buttons)

            # 添加查看最新作品按钮
            keyboard.append([InlineKeyboardButton("📰 查看所有收藏的最新作品", callback_data="favlatest:all")])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await q.edit_message_text(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            return

        if data.startswith("favquery:"):
            # 查询单个收藏女优
            actress_name = data[len("favquery:"):]
            user = update.effective_user
            favorites_manager = get_favorites_manager()

            # 记录查询历史
            favorites_manager.record_favorite_query(user.id, actress_name)

            await q.answer(f"正在查询 {actress_name}...")
            user = update.effective_user
            await run_search_reply(q.message, actress_name, user.id if user else None)
            
        elif data.startswith("favnow:"):
            # 即时收藏
            actress_name = data[len("favnow:"):]
            user = update.effective_user
            favorites_manager = get_favorites_manager()
            
            # 先查询女优信息
            try:
                profile = await asyncio.to_thread(service.query_profile, actress_name)
                if not profile.found:
                    await q.answer(f"未找到女优: {actress_name}", show_alert=True)
                    return
                
                # 添加收藏
                success = favorites_manager.add_favorite(
                    user_id=user.id,
                    actress_name=profile.star_name,
                    actress_id=profile.star_id,
                    actress_data={
                        'star_name': profile.star_name,
                        'star_id': profile.star_id,
                        'wiki_url': profile.wiki_url,
                        'extra_info': profile.extra_info
                    }
                )
                
                if success:
                    await q.answer(f"✅ 已收藏: {profile.star_name}")
                    
                    # 更新按钮状态
                    new_keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("⭐ 已收藏", callback_data=f"unfavnow:{profile.star_name}"),
                            InlineKeyboardButton("📰 查看最新作品", callback_data=f"favquery:{profile.star_name}")
                        ]
                    ])
                    
                    # 尝试更新消息的回复标记
                    try:
                        if q.message.caption:
                            # 图片消息
                            await q.edit_message_caption(
                                reply_markup=new_keyboard
                            )
                        else:
                            # 文本消息
                            await q.edit_message_reply_markup(
                                reply_markup=new_keyboard
                            )
                    except Exception:
                        pass  # 忽略更新失败
                else:
                    await q.answer("收藏失败", show_alert=True)
                    
            except Exception as exc:
                logging.exception("即时收藏失败: %s", exc)
                await q.answer("收藏失败", show_alert=True)
                
        elif data.startswith("unfavnow:"):
            # 即时取消收藏
            actress_name = data[len("unfavnow:"):]
            user = update.effective_user
            favorites_manager = get_favorites_manager()
            
            # 移除收藏
            success = favorites_manager.remove_favorite(user.id, actress_name)
            
            if success:
                await q.answer(f"✅ 已取消收藏: {actress_name}")
                
                # 更新按钮状态
                new_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("☆ 收藏", callback_data=f"favnow:{actress_name}"),
                        InlineKeyboardButton("📰 查看最新作品", callback_data=f"favquery:{actress_name}")
                    ]
                ])
                
                # 尝试更新消息的回复标记
                try:
                    if q.message.caption:
                        # 图片消息
                        await q.edit_message_caption(
                            reply_markup=new_keyboard
                        )
                    else:
                        # 文本消息
                        await q.edit_message_reply_markup(
                            reply_markup=new_keyboard
                        )
                except Exception:
                    pass  # 忽略更新失败
            else:
                await q.answer("取消收藏失败", show_alert=True)
            
        elif data == "favlatest:all":
            # 查看所有收藏的最新作品
            await q.answer("正在查询所有收藏的最新作品...")
            await favorites_latest_cmd(update, context)

    async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理主菜单回调"""
        q = update.callback_query
        if not q or not q.message:
            return
        if not is_allowed(update):
            await q.answer("无权限使用", show_alert=True)
            return
        
        data = q.data or ""
        
        if data.startswith("menu:"):
            action = data[len("menu:"):]
            
            if action == "search":
                await q.answer("请发送女优名字进行查询")
                await q.message.reply_text("🔍 请发送女优名字进行查询，例如：\n三上悠亚\n明日花キララ\nYua Mikami")
            elif action == "magnet":
                await q.answer("请发送关键词或番号进行磁力搜索")
                await q.message.reply_text("💾 请发送关键词或番号进行磁力搜索，例如：\nSSIS-123\n三上悠亚")
            elif action == "rank":
                await q.answer("正在获取热门女优排行榜...")
                # 调用rank_cmd函数，使用默认参数
                await rank_cmd(update, context)
            elif action == "favorites":
                await q.answer("正在获取我的收藏...")
                # 调用my_favorites_cmd函数
                await my_favorites_cmd(update, context)
            elif action == "help":
                await q.answer("显示帮助信息")
                # 调用help_cmd函数
                await help_cmd(update, context)
            else:
                await q.answer()
        elif data.startswith("search:"):
            # 处理搜索回调
            query = data[len("search:"):]
            await q.answer(f"正在搜索：{query}")
            await run_search_reply(q.message, query, update.effective_user.id if update.effective_user else None)
        elif data.startswith("magnet:"):
            # 处理磁力搜索回调
            query = data[len("magnet:"):]
            await q.answer(f"正在搜索磁力：{query}")
            await run_magnet_reply(q.message, query)

    async def rank_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        q = update.callback_query
        if not q or not q.message:
            return
        if not is_allowed(update):
            await q.answer("无权限使用", show_alert=True)
            return
        data = q.data or ""
        
        # 处理重试回调
        retry_match = re.match(r"^rank_retry:(\d{1,2}):(\d)$", data)
        if retry_match:
            limit = int(retry_match.group(1))
            page = int(retry_match.group(2))
            limit = max(1, min(limit, 50))
            page = max(1, min(page, 5))
            
            await q.answer("正在重试...")
            try:
                stars = await asyncio.to_thread(service.get_hot_star_rankings, limit, page)
                if not stars:
                    # 尝试使用缓存数据
                    cached_stars = service.rank_cache.get(("rank", limit, page))
                    if cached_stars:
                        await q.edit_message_text(
                            f"<b>热门女优排行榜</b>\n" +
                            f"来源：DMM 官方月榜（第{page}页）\n" +
                            f"⚠️ 最新数据获取失败，显示缓存数据\n\n" +
                            format_rankings(cached_stars, page),
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=build_rank_keyboard(limit, page),
                        )
                    else:
                        await q.edit_message_text(
                            "<b>热门女优排行榜</b>\n" +
                            "来源：DMM 官方月榜\n\n" +
                            "暂时无法获取榜单，请稍后再试。\n" +
                            "点击下方按钮重试：",
                            parse_mode=ParseMode.HTML,
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔄 重试", callback_data=f"rank_retry:{limit}:{page}")]
                            ])
                        )
                else:
                    await q.edit_message_text(
                        format_rankings(stars, page),
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=build_rank_keyboard(limit, page),
                    )
            except Exception as exc:
                logging.exception("rank retry failed: %s", exc)
                await q.edit_message_text(
                    "<b>热门女优排行榜</b>\n" +
                    "来源：DMM 官方月榜\n\n" +
                    "获取榜单失败，请稍后再试。\n" +
                    "点击下方按钮重试：",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 重试", callback_data=f"rank_retry:{limit}:{page}")]
                    ])
                )
            return
        
        # 处理普通分页回调
        m = re.match(r"^rank:(\d{1,2}):(\d):([01])$", data)
        if not m:
            await q.answer()
            return

        limit = int(m.group(1))
        page = int(m.group(2))
        with_avatars = m.group(3) == "1"
        limit = max(1, min(limit, 50))
        page = max(1, min(page, 5))

        await q.answer("加载中...")
        try:
            stars = await asyncio.to_thread(service.get_hot_star_rankings, limit, page)
            if not stars:
                # 尝试使用缓存数据
                cached_stars = service.rank_cache.get(("rank", limit, page))
                if cached_stars:
                    await q.edit_message_text(
                        f"<b>热门女优排行榜</b>\n" +
                        f"来源：DMM 官方月榜（第{page}页）\n" +
                        f"⚠️ 最新数据获取失败，显示缓存数据\n\n" +
                        format_rankings(cached_stars, page),
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=build_rank_keyboard(limit, page),
                    )
                else:
                    await q.edit_message_text(
                        "<b>热门女优排行榜</b>\n" +
                        "来源：DMM 官方月榜\n\n" +
                        "暂时无法获取榜单，请稍后再试。\n" +
                        "点击下方按钮重试：",
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 重试", callback_data=f"rank_retry:{limit}:{page}")]
                        ])
                    )
            else:
                await q.edit_message_text(
                    format_rankings(stars, page),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=build_rank_keyboard(limit, page),
                )
                if with_avatars:
                    await send_rank_avatars_for_page(q.message, stars, page, limit)
        except Exception as exc:
            logging.exception("rank callback failed: %s", exc)
            try:
                await q.edit_message_text(
                    "<b>热门女优排行榜</b>\n" +
                    "来源：DMM 官方月榜\n\n" +
                    "获取榜单失败，请稍后再试。\n" +
                    "点击下方按钮重试：",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 重试", callback_data=f"rank_retry:{limit}:{page}")]
                    ])
                )
            except Exception:
                pass

    async def check_and_push_new_works(context: ContextTypes.DEFAULT_TYPE) -> None:
        """定时检查并推送新作品"""
        try:
            if not push_enabled_global:
                logging.info("推送功能全局关闭，跳过检查")
                return
            
            logging.info("开始检查新作品推送")
            favorites_manager = get_favorites_manager()
            
            try:
                user_ids = favorites_manager.get_users_with_push_enabled()
                logging.info(f"找到 {len(user_ids)} 个开启推送的用户")
            except Exception as e:
                logging.error(f"获取推送用户列表失败: {e}")
                return
            
            profile_cache = {}
            request_delay = 1.0
            batch_size = 5
            
            for batch_start in range(0, len(user_ids), batch_size):
                batch_end = min(batch_start + batch_size, len(user_ids))
                user_batch = user_ids[batch_start:batch_end]
                logging.info(f"处理用户批次 {batch_start + 1}-{batch_end}")
                
                for user_id in user_batch:
                    if allowed_user_ids and user_id not in allowed_user_ids:
                        continue
                        
                    try:
                        logging.info(f"检查用户 {user_id} 的收藏女优")
                        
                        try:
                            favorites = favorites_manager.get_favorites(user_id, limit=100)
                        except Exception as e:
                            logging.error(f"获取用户 {user_id} 收藏失败: {e}")
                            continue
                        
                        new_works_for_user = []
                        
                        for fav in favorites:
                            actress_name = fav.get('actress_name')
                            if not actress_name:
                                continue
                            
                            try:
                                logging.debug(f"检查女优 {actress_name} 的新作品")
                                
                                if actress_name in profile_cache:
                                    profile = profile_cache[actress_name]
                                    logging.debug(f"使用缓存的女优资料: {actress_name}")
                                else:
                                    profile = await asyncio.to_thread(service.query_profile, actress_name)
                                    profile_cache[actress_name] = profile
                                    await asyncio.sleep(request_delay)
                                
                                if not profile.found or not profile.latest_works:
                                    continue
                                
                                for work in profile.latest_works:
                                    av_id = work.get('id')
                                    if not av_id:
                                        continue
                                    
                                    try:
                                        is_new = favorites_manager.record_actress_work(
                                            actress_name=actress_name,
                                            av_id=av_id,
                                            title=work.get('title'),
                                            date=work.get('date'),
                                            url=work.get('url'),
                                            img=work.get('img')
                                        )
                                        
                                        if is_new:
                                            logging.info(f"发现新作品: {actress_name} - {av_id}")
                                            new_works_for_user.append({
                                                'actress_name': actress_name,
                                                'work': work
                                            })
                                    except Exception as e:
                                        logging.error(f"记录作品 {actress_name} - {av_id} 失败: {e}")
                                        continue
                            except Exception as e:
                                logging.error(f"检查女优 {actress_name} 失败: {e}")
                                continue
                        
                        if new_works_for_user:
                            logging.info(f"为用户 {user_id} 推送 {len(new_works_for_user)} 个新作品")
                            for item in new_works_for_user:
                                try:
                                    await send_new_work_notification(context.bot, user_id, item['actress_name'], item['work'])
                                    await asyncio.sleep(0.5)
                                except Exception as e:
                                    logging.error(f"推送作品给用户 {user_id} 失败: {e}")
                                    continue
                        
                        try:
                            favorites_manager.update_last_check(user_id)
                        except Exception as e:
                            logging.error(f"更新用户 {user_id} 检查时间失败: {e}")
                            
                    except Exception as e:
                        logging.error(f"处理用户 {user_id} 时发生异常: {e}", exc_info=True)
                        continue
                
                if batch_end < len(user_ids):
                    logging.info(f"批次处理完成，等待 {batch_size} 秒后继续...")
                    await asyncio.sleep(batch_size)
            
            logging.info(f"新作品检查完成，缓存了 {len(profile_cache)} 个女优资料")
        except Exception as e:
            logging.error(f"推送检查任务发生未预期异常: {e}", exc_info=True)
    
    async def send_new_work_notification(bot, user_id: int, actress_name: str, work: dict):
        """发送新作品通知"""
        try:
            av_id = work.get('id', '未知')
            av_date = work.get('date', '未知')
            av_title = work.get('title', '')
            img = work.get('img', '')
            
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
                [InlineKeyboardButton(f"🧲 搜索 {av_id} 磁力", callback_data=f"magnet:{av_id}")],
                [InlineKeyboardButton(f"👩 查询 {actress_name}", callback_data=f"favquery:{actress_name}")]
            ])
            
            if img:
                try:
                    img_bytes = await asyncio.to_thread(download_image, img, proxy_addr)
                    
                    short_caption = f"🎉 {html.escape(actress_name)} 更新了！\n🎬 <code>{html.escape(av_id)}</code>"
                    
                    if img_bytes:
                        await bot.send_photo(
                            chat_id=user_id,
                            photo=img_bytes,
                            caption=short_caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard
                        )
                    else:
                        await bot.send_photo(
                            chat_id=user_id,
                            photo=img,
                            caption=short_caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard
                        )
                    
                    await bot.send_message(
                        chat_id=user_id,
                        text=full_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logging.warning(f"发送封面失败，发送纯文本: {e}")
                    await bot.send_message(
                        chat_id=user_id,
                        text=full_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=keyboard
                    )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=full_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )
        except Exception as e:
            logging.error(f"发送新作品通知失败: {e}")
    
    async def push_toggle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """推送开关命令"""
        msg = update.effective_message
        if not msg:
            return
        if not is_allowed(update):
            await msg.reply_text("无权限使用此机器人。")
            return
        
        user = update.effective_user
        favorites_manager = get_favorites_manager()
        
        if not context.args:
            settings = favorites_manager.get_push_settings(user.id)
            status = "✅ 已开启" if settings.get('push_enabled', True) else "❌ 已关闭"
            await msg.reply_text(
                f"📰 新作品推送状态：{status}\n\n"
                "使用 /push on 开启推送\n"
                "使用 /push off 关闭推送"
            )
            return
        
        action = context.args[0].lower()
        if action in ['on', 'enable', '开启']:
            favorites_manager.set_push_enabled(user.id, True)
            await msg.reply_text("✅ 已开启新作品推送\n\n当你关注的女优有新作品时，我会及时通知你！")
        elif action in ['off', 'disable', '关闭']:
            favorites_manager.set_push_enabled(user.id, False)
            await msg.reply_text("❌ 已关闭新作品推送")
        else:
            await msg.reply_text("用法：/push [on|off]")
    
    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if not msg or not msg.text:
            return
        if not is_allowed(update):
            await msg.reply_text("无权限使用此机器人。")
            return

        query = msg.text.strip()
        if not query:
            return

        if looks_like_av_id(query):
            await run_magnet_reply(msg, query)
            return

        user = update.effective_user
        await run_search_reply(msg, query, user.id if user else None)

    async def post_init(application: Application) -> None:
        logging.info("开始执行post_init函数")
        # 初始化收藏管理器，确保数据库文件创建
        logging.info("初始化收藏管理器")
        from .favorites import get_favorites_manager
        get_favorites_manager()
        logging.info("收藏管理器初始化完成")
        
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
            
            # 发送启动提示消息到指定的用户或频道
            # 可以在环境变量中配置接收启动消息的用户ID
            admin_user_id = os.getenv("ADMIN_USER_ID")
            logging.info(f"Admin user ID: {admin_user_id}")
            if admin_user_id:
                try:
                    logging.info(f"发送启动消息到用户: {admin_user_id}")
                    await application.bot.send_message(
                        chat_id=int(admin_user_id),
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
                    logging.error(f"发送启动消息失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                logging.warning("ADMIN_USER_ID环境变量未设置，跳过发送启动消息")
        except Exception as exc:
            logging.error("设置命令菜单失败: %s", exc)
            import traceback
            traceback.print_exc()
        logging.info("post_init函数执行完成")

    app = Application.builder().token(token).post_init(post_init).build()
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
    app.add_handler(CallbackQueryHandler(rank_page_callback, pattern=r"^rank:"))
    app.add_handler(CallbackQueryHandler(favorite_query_callback, pattern=r"^(fav|myfav)"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:|^search:|^magnet:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    
    if push_enabled_global:
        job_queue = app.job_queue
        job_queue.run_repeating(
            check_and_push_new_works,
            interval=push_check_interval,
            first=10
        )
        logging.info(f"已启用新作品推送检查，间隔: {push_check_interval}秒")
    
    return app


def main() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("jvav.utils").setLevel(logging.CRITICAL)

    app = build_app()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
