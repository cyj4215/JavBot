from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ActressProfile:
    found: bool
    query: str
    star_name: Optional[str] = None
    star_id: Optional[str] = None
    wiki_title: Optional[str] = None
    wiki_url: Optional[str] = None
    latest_works: Optional[List[Dict[str, Any]]] = None
    top_ids: Optional[List[str]] = None
    top_works: Optional[List[Dict[str, Any]]] = None
    suggestions: Optional[List[str]] = None
    matched_name: Optional[str] = None
    extra_info: Optional[Dict[str, Any]] = None
