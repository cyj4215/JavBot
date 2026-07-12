"""Async HTTP session with retry support."""
from __future__ import annotations

import httpx


class BotSession:
    """Async HTTP session, connection-level retry.

    Usage:
        session = BotSession(proxy=...)
        await session.client.get(...)
        await session.client.aclose()  # on shutdown
    """

    def __init__(self, proxy: str = ""):
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        transport = httpx.AsyncHTTPTransport(retries=3)
        self._client = httpx.AsyncClient(
            limits=limits,
            transport=transport,
            timeout=httpx.Timeout(20.0),
            proxy=proxy if proxy else None,
        )

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client
