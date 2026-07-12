from __future__ import annotations

from pydantic import BaseModel

from .wiki import WikiExtra
from .works import MergedWork


class ActressProfile(BaseModel):
    found: bool
    query: str
    star_name: str | None = None
    star_id: str | None = None
    wiki_title: str | None = None
    wiki_url: str | None = None
    latest_works: list[MergedWork] | None = None
    suggestions: list[str] | None = None
    matched_name: str | None = None
    extra_info: WikiExtra | None = None
    avatar_url: str | None = None
