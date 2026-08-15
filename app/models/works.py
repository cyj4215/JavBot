from __future__ import annotations

from pydantic import BaseModel

from .magnets import MagnetLink


class JavBusWork(BaseModel):
    id: str
    title: str = ""
    date: str = "未知"
    img: str = ""
    url: str = ""
    magnets: list[MagnetLink] = []
    stars: list[str] = []


class JavDbWork(BaseModel):
    id: str
    title: str = ""
    date: str = "未知"
    img: str = ""
    url: str = ""


class MergedWork(BaseModel):
    id: str
    title: str = ""
    date: str = "未知"
    img: str = ""
    url: str = ""
