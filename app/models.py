from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ActressProfile:
    found: bool
    query: str
    star_name: str | None = None
    star_id: str | None = None
    wiki_title: str | None = None
    wiki_url: str | None = None
    latest_works: list[dict[str, Any]] | None = None
    suggestions: list[str] | None = None
    matched_name: str | None = None
    extra_info: dict[str, Any] | None = None
    avatar_url: str | None = None
