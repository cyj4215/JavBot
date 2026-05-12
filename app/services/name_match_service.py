from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from pypinyin import pinyin, Style

from .text_utils import contains_cjk, normalize_name

if TYPE_CHECKING:
    from jvav import JavBusUtil
    from ..rate_limiter import RateLimiter


class NameMatchService:
    """姓名匹配与别名查找子服务。"""

    def __init__(
        self,
        javbus_util: "JavBusUtil",
        s2t,
        t2s,
        javbus_limiter: "RateLimiter",
        alias_map: Optional[Dict[str, str]] = None,
    ):
        self.javbus = javbus_util
        self.s2t = s2t
        self.t2s = t2s
        self._javbus_limiter = javbus_limiter
        self._alias_map = alias_map if alias_map is not None else self._default_alias_map()

    @property
    def alias_map(self) -> Dict[str, str]:
        return self._alias_map

    def name_candidates(self, name: str) -> List[str]:
        seen: set = set()
        candidates: List[str] = []

        def add(v: str) -> None:
            vv = normalize_name(v)
            if vv and vv not in seen:
                seen.add(vv)
                candidates.append(vv)

        if name in self._alias_map:
            add(self._alias_map[name])

        add(name)
        no_space = name.replace(" ", "")
        add(no_space)

        if contains_cjk(name):
            add(self._to_traditional(name))
            add(self._to_simplified(name))
            add(self._to_traditional(no_space))
            add(self._to_simplified(no_space))

            try:
                pinyin_result = pinyin(name, style=Style.NORMAL)
                pinyin_parts = [i[0] for i in pinyin_result]
                add(" ".join(pinyin_parts))
                add("".join(pinyin_parts))
                add("".join(p[0].lower() for p in pinyin_parts))
            except Exception:
                logging.getLogger(__name__).debug("拼音转换失败", exc_info=True)
        return candidates

    def find_star(self, candidates: List[str]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        for cand in candidates:
            try:
                self._javbus_limiter.wait()
                code, star = self.javbus.check_star_exists(cand)
                if code == 200 and star:
                    return cand, star
            except Exception:
                logging.getLogger(__name__).debug("查找明星失败: candidate=%s", cand, exc_info=True)
        for cand in candidates:
            try:
                self._javbus_limiter.wait()
                code, names = self.javbus.fuzzy_search_stars(cand)
                if code == 200 and names:
                    for n in names[:3]:
                        self._javbus_limiter.wait()
                        code2, star = self.javbus.check_star_exists(n)
                        if code2 == 200 and star:
                            return cand, star
            except Exception:
                logging.getLogger(__name__).debug("模糊搜索失败: candidate=%s", cand, exc_info=True)
        return None, None

    def _to_traditional(self, text: str) -> str:
        if not self.s2t:
            return text
        try:
            return self.s2t.convert(text)
        except Exception:
            logging.getLogger(__name__).debug("简繁转换失败", exc_info=True)
            return text

    def _to_simplified(self, text: str) -> str:
        if not self.t2s:
            return text
        try:
            return self.t2s.convert(text)
        except Exception:
            logging.getLogger(__name__).debug("繁简转换失败", exc_info=True)
            return text

    @staticmethod
    def _default_alias_map() -> Dict[str, str]:
        return {
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
            "河北彩花": "河北彩花",
        }
