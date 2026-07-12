from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from .actors import StarInfo
from .wiki import WikiExtra
from .works import MergedWork


class ActressProfile(BaseModel):
    found: bool
    query: str
    star_name: Optional[str] = None
    star_id: Optional[str] = None
    wiki_title: Optional[str] = None
    wiki_url: Optional[str] = None
    latest_works: Optional[list[MergedWork]] = None
    suggestions: Optional[list[str]] = None
    matched_name: Optional[str] = None
    extra_info: Optional[WikiExtra] = None
    avatar_url: Optional[str] = None
