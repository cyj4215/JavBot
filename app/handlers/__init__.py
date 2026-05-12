from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..config import BotConfig
    from ..service import ActressService


@dataclass
class _SharedState:
    config: BotConfig
    service: ActressService


_shared: Optional[_SharedState] = None


def _set_shared(config: BotConfig, service: ActressService) -> None:
    global _shared
    _shared = _SharedState(config=config, service=service)


def _get_shared() -> _SharedState:
    if _shared is None:
        raise RuntimeError("Shared state not initialized. Call _set_shared() first.")
    return _shared
