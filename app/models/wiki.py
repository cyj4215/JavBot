from __future__ import annotations
from pydantic import BaseModel


class SocialLink(BaseModel):
    label: str = "链接"
    url: str


class WikiExtra(BaseModel):
    birth_date: str = ""
    height: str = ""
    measurements: str = ""
    cup: str = ""
    socials: list[SocialLink] = []
