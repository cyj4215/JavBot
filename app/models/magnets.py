from __future__ import annotations
from pydantic import BaseModel


class MagnetLink(BaseModel):
    title: str
    magnet: str
    size: str = "Unknown"
