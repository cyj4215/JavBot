from __future__ import annotations
from pydantic import BaseModel


class ActorSearchResult(BaseModel):
    name: str
    url: str
    avatar: str = ""


class StarInfo(BaseModel):
    star_name: str
    star_id: str
