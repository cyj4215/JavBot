from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List
from urllib.parse import unquote, urlparse

import requests
import wikipediaapi
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from ..cache import TTLCache
    from ..rate_limiter import RateLimiter


class WikiService:
    """维基百科 / Wikidata 信息提取子服务。"""

    def __init__(
        self,
        proxy_addr: str,
        wiki_user_agent: str,
        http_session: requests.Session,
        wiki_page_cache: "TTLCache",
        wiki_limiter: "RateLimiter",
    ):
        self.proxy_addr = proxy_addr
        self.wiki_user_agent = wiki_user_agent
        self.http = http_session
        self.wiki_page_cache = wiki_page_cache
        self._wiki_limiter = wiki_limiter
        self._wiki_instances: Dict[str, wikipediaapi.Wikipedia] = {}

    def _get_wiki(self, lang: str) -> wikipediaapi.Wikipedia:
        if lang not in self._wiki_instances:
            self._wiki_instances[lang] = wikipediaapi.Wikipedia(
                language=lang, user_agent=self.wiki_user_agent
            )
        return self._wiki_instances[lang]

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def wiki_page_by_lang(
        self, topic: str, from_lang: str, to_lang: str
    ) -> Dict[str, Any]:
        logger = logging.getLogger(__name__)

        cache_key = ("wiki_page", topic, from_lang, to_lang)
        cached = self.wiki_page_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"从缓存获取wiki_page: {cache_key} -> {cached}")
            return cached

        logger.debug(f"开始查询维基百科: topic={topic}, from_lang={from_lang}, to_lang={to_lang}")
        try:
            self._wiki_limiter.wait()
            wiki = self._get_wiki(from_lang)
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
            logger.warning("维基百科查询异常: %s", e, exc_info=True)
            return {}

    def wiki_aliases(self, name: str) -> List[str]:
        from .text_utils import contains_cjk, normalize_name

        aliases: List[str] = []
        seen: set = set()

        def add(v: str) -> None:
            vv = normalize_name(v)
            if vv and vv not in seen:
                seen.add(vv)
                aliases.append(vv)

        if contains_cjk(name):
            p = self.wiki_page_by_lang(name, from_lang="zh", to_lang="ja")
            add(p.get("title", ""))
            p = self.wiki_page_by_lang(name, from_lang="zh", to_lang="en")
            add(p.get("title", ""))
        else:
            p = self.wiki_page_by_lang(name, from_lang="en", to_lang="ja")
            add(p.get("title", ""))
        return aliases

    def get_star_extra_info(self, wiki_url: str) -> Dict[str, Any]:
        logger = logging.getLogger(__name__)

        info: Dict[str, Any] = {"birth_date": "", "height": "", "measurements": "", "cup": "", "socials": []}
        if not wiki_url:
            logger.debug("wiki_url为空，无法获取extra_info")
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

        socials: List[Dict[str, str]] = []
        seen: set = set()
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

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _extract_wikidata_entity_id(self, wiki_url: str) -> str:
        try:
            self._wiki_limiter.wait()
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
            logging.getLogger(__name__).debug("提取Wikidata实体ID失败: wiki_url=%s", wiki_url, exc_info=True)
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

    def _extract_info_from_wikidata(self, wiki_url: str) -> Dict[str, Any]:
        info: Dict[str, Any] = {"birth_date": "", "height": "", "measurements": "", "cup": "", "socials": []}
        qid = self._extract_wikidata_entity_id(wiki_url)
        if not qid:
            return info
        try:
            self._wiki_limiter.wait()
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

            for item in claims.get("P569") or []:
                dv = (((item or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
                birth = self._format_wikidata_time(dv.get("time", ""))
                if birth:
                    info["birth_date"] = birth
                    break

            for item in claims.get("P2048") or []:
                dv = (((item or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
                amount_raw = dv.get("amount", "")
                unit = dv.get("unit", "")
                if not amount_raw:
                    continue
                try:
                    amount = abs(float(amount_raw))
                except Exception:
                    logging.getLogger(__name__).debug("解析身高数值失败: %s", amount_raw, exc_info=True)
                    continue
                if unit.endswith("/Q11573"):
                    info["height"] = f"{round(amount * 100)} cm"
                else:
                    info["height"] = f"{amount:g}"
                break

            socials: List[Dict[str, str]] = []
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
            logging.getLogger(__name__).debug("从Wikidata提取信息失败: wiki_url=%s", wiki_url, exc_info=True)
            return info
        return info

    def _extract_info_from_wikipedia(self, wiki_url: str) -> Dict[str, Any]:
        info: Dict[str, Any] = {"birth_date": "", "height": "", "measurements": "", "cup": "", "socials": []}
        try:
            self._wiki_limiter.wait()
            resp = self.http.get(
                wiki_url,
                timeout=20,
                headers={"user-agent": self.wiki_user_agent},
            )
            if resp.status_code != 200:
                return info
            soup = BeautifulSoup(resp.text, "lxml")
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

            socials: List[Dict[str, str]] = []
            seen_urls: set = set()
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
                    if href not in seen_urls:
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
                        seen_urls.add(href)
            info["socials"] = socials
        except Exception:
            logging.getLogger(__name__).debug("从Wikipedia提取信息失败: wiki_url=%s", wiki_url, exc_info=True)
            return info
        return info
