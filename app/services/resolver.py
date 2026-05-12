from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from jvav import JavBusUtil
    from ..rate_limiter import RateLimiter
    from .name_match_service import NameMatchService
    from .wiki_service import WikiService


class ProfileResolver:
    """Name resolution: candidates -> find_star -> wiki aliases -> fuzzy fallback."""

    def __init__(
        self,
        name_match_svc: NameMatchService,
        wiki_svc: WikiService,
        javbus: JavBusUtil,
        javbus_limiter: RateLimiter,
    ):
        self._name_match_svc = name_match_svc
        self._wiki_svc = wiki_svc
        self.javbus = javbus
        self._javbus_limiter = javbus_limiter

    def resolve(self, name: str) -> Tuple[Optional[str], Optional[Dict], List[str]]:
        """Resolve a query string to an actress.

        Returns (matched_name, star_dict, suggestions).
        star_dict is None when no match is found.
        """
        candidates = self._name_match_svc.name_candidates(name)
        matched_name, star = self._name_match_svc.find_star(candidates)

        if not star:
            for cand in list(candidates):
                for alias in self._wiki_svc.wiki_aliases(cand):
                    if alias not in candidates:
                        candidates.append(alias)
            matched_name, star = self._name_match_svc.find_star(candidates)

        suggestions: list = []
        if not star:
            seen: set = set()
            for cand in candidates[:4]:
                self._javbus_limiter.wait()
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

        return matched_name, star, suggestions
