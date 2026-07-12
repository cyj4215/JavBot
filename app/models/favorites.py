from __future__ import annotations
from pydantic import BaseModel


class FavoriteEntry(BaseModel):
    actress_name: str
    created_at: str = ""
    last_query_at: str = ""
    push_enabled: bool = True
    actress_id: str = ""
