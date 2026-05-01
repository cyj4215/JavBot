"""Test that query_profile_async does not block the asyncio event loop."""
import asyncio
import time

import pytest


class TestQueryProfileAsync:
    """Verify event loop stays responsive during actress queries."""

    @pytest.mark.asyncio
    async def test_event_loop_not_blocked(self, monkeypatch):
        """A concurrent task should make progress while query_profile_async runs.

        The old code inlined name resolution directly inside
        query_profile_async, calling RateLimiter.time.sleep() and sync
        HTTP calls on the main thread -- blocking the event loop.

        The fix moved that logic into _resolve_name_sync(), a sync method
        called via asyncio.to_thread() so blocking calls stay in a thread
        pool and the event loop remains responsive.

        This test creates a heartbeat coroutine concurrently with the
        profile query.  It uses return_when=FIRST_COMPLETED so that if the
        heartbeat finishes first it proves the event loop stayed free
        during the query; if the query finishes first it proves the
        event loop was blocked.
        """
        from app.service import ActressService

        svc = ActressService()

        # Mock blocking API methods so they run fast but still exercise
        # the thread-pool path.  A 0.5s sleep simulates the effect of a
        # RateLimiter wait plus a network call -- long enough that the
        # heartbeat (3 ticks x 0.02s = 0.06s) finishes first when the
        # event loop stays responsive.
        monkeypatch.setattr(
            svc._name_match_svc,
            "find_star",
            lambda candidates: time.sleep(0.5) or (None, None),
        )
        monkeypatch.setattr(
            svc._wiki_svc,
            "wiki_aliases",
            lambda *a, **kw: [],
        )
        monkeypatch.setattr(
            svc.javbus,
            "fuzzy_search_stars",
            lambda name: (404, []),
        )

        heartbeat_ticks = []

        async def heartbeat():
            while len(heartbeat_ticks) < 3:
                heartbeat_ticks.append(time.monotonic())
                await asyncio.sleep(0.02)

        query_task = asyncio.create_task(
            svc.query_profile_async("test_nonexistent_actress_xyz")
        )
        heartbeat_task = asyncio.create_task(heartbeat())

        done, _ = await asyncio.wait(
            [query_task, heartbeat_task],
            timeout=15.0,
            return_when=asyncio.FIRST_COMPLETED,
        )

        # If the heartbeat finished first, the event loop was free.
        # If the query finished first (or we hit the 15s timeout),
        # the event loop was blocked.
        assert heartbeat_task in done, (
            f"Event loop blocked: heartbeat only got {len(heartbeat_ticks)} ticks. "
            "RateLimiter.time.sleep() is likely blocking the main thread."
        )

        # Heartbeat is done, but we should still await the query so any
        # exception propagates.
        result = await query_task
        assert result.found is False
