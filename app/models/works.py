from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class JavBusWork(BaseModel):
    id: str
    title: str = ""
    date: str = "未知"
    img: str = ""
    url: str = ""
    magnets: list[dict] = []


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
