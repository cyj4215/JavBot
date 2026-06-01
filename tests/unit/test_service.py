"""Tests for ActressService facade: query_profile_async with mocked sub-services."""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# jvav native module not available in test env — mock at module level
_jvav_mock = MagicMock()
_jvav_mock.JavBusUtil = MagicMock
sys.modules["jvav"] = _jvav_mock

from app.models import ActressProfile
from app.service import ActressService


@pytest.fixture
def svc():
    """ActressService with mocked sub-services injected via constructor."""
    from app.services import WikiService, JavBusService, NameMatchService
    s = ActressService(
        latest_limit=5,
        top_limit=5,
        profile_cache_ttl=3600,
        wiki_service=MagicMock(spec=WikiService),
        javbus_service=MagicMock(spec=JavBusService),
        name_match_service=MagicMock(spec=NameMatchService),
    )
    return s


def _mock_resolver_result(svc, matched_name="三上悠亜", star_name="三上悠亜", star_id="SSIS-123", found=True):
    """Set up _resolver.resolve to return given star."""
    if found:
        svc._resolver.resolve = MagicMock(return_value=(
            matched_name,
            {"star_name": star_name, "star_id": star_id},
            [],
        ))
    else:
        svc._resolver.resolve = MagicMock(return_value=(
            "query",
            None,
            ["Suggestion A", "Suggestion B"],
        ))
    return svc


def _mock_javbus_latest(svc, ids=None):
    """Set up javbus.get_new_ids_by_star_name + build_latest_works."""
    if ids is None:
        ids = ["TEST-001", "TEST-002", "TEST-003"]
    svc.javbus.get_new_ids_by_star_name = MagicMock(return_value=(200, ids))
    svc._javbus_svc.build_latest_works = MagicMock(return_value=[
        {"id": "TEST-001", "img": "https://javbus.com/cover/001.jpg", "date": "2026-05-03"},
        {"id": "TEST-002", "img": "https://javbus.com/cover/002.jpg", "date": "2026-05-02"},
        {"id": "TEST-003", "img": "https://javbus.com/cover/003.jpg", "date": "2026-05-01"},
    ])


def _mock_wiki(svc, title="三上悠亜", url="https://zh.wikipedia.org/wiki/三上悠亜"):
    """Set up wiki service returns."""
    svc._wiki_svc.wiki_page_by_lang = MagicMock(return_value={"title": title, "url": url})
    svc._wiki_svc.get_star_extra_info = MagicMock(return_value={
        "birth_date": "1993-08-19",
        "height": "160cm",
        "measurements": "88-58-88",
        "cup": "E",
        "socials": [
            {"label": "Twitter", "url": "https://twitter.com/mikami_yua"},
        ],
    })
    return svc


def _mock_javdb_scraper(svc, works=None, avatar="https://javdb.com/avatar/test.jpg"):
    """Set up JavDb scraper returns."""
    if works is None:
        works = [
            {"id": "TEST-004", "img": "https://javdb.com/cover/004.jpg", "date": "2026-05-04"},
        ]
    svc._javdb_scraper.get_actress_works = AsyncMock(return_value=works)
    svc._javdb_scraper.search_actress = AsyncMock(return_value={
        "name": "三上悠亜",
        "url": "https://javdb.com/actors/abc",
        "avatar": avatar,
    })
    return svc


class TestQueryProfileAsync:
    """query_profile_async: cache behavior, gather fan-out, error handling, data merging."""

    async def test_cache_hit_returns_fast(self, svc):
        """Cache hit → returns cached ActressProfile without calling sub-services."""
        cached = ActressProfile(found=True, query="test", star_name="Cached", star_id="C-001")
        svc.profile_cache.set(("profile", "test", 5, 5), cached.__dict__)
        svc._resolver.resolve = MagicMock(side_effect=AssertionError("should not be called"))

        result = await svc.query_profile_async("test")
        assert result.found
        assert result.star_name == "Cached"

    async def test_cache_miss_calls_resolver(self, svc):
        """Cache miss → resolver called with name."""
        _mock_resolver_result(svc, star_name="三上悠亜")
        _mock_javbus_latest(svc, ids=[])
        _mock_wiki(svc)
        _mock_javdb_scraper(svc, works=[])

        result = await svc.query_profile_async("三上悠亜")
        assert result.found

    async def test_not_found_returns_suggestions(self, svc):
        """Resolver returns None → profile with suggestions."""
        svc._resolver.resolve = MagicMock(return_value=("unknown", None, ["Hint A", "Hint B"]))

        result = await svc.query_profile_async("unknown")
        assert not result.found
        assert result.suggestions == ["Hint A", "Hint B"]

    async def test_profile_has_minimal_fields(self, svc):
        """Found profile has star_name, star_id, extra_info, avatar_url."""
        _mock_resolver_result(svc)
        _mock_javbus_latest(svc)
        _mock_wiki(svc)
        _mock_javdb_scraper(svc)

        result = await svc.query_profile_async("三上悠亜")
        assert result.found
        assert result.star_name == "三上悠亜"
        assert result.star_id == "SSIS-123"
        assert result.extra_info["birth_date"] == "1993-08-19"
        assert result.avatar_url == "https://javdb.com/avatar/test.jpg"

    async def test_latest_works_from_javbus(self, svc):
        """JavBus works appear in latest_works."""
        _mock_resolver_result(svc)
        _mock_javbus_latest(svc)
        _mock_wiki(svc)
        _mock_javdb_scraper(svc, works=[])

        result = await svc.query_profile_async("三上悠亜")
        assert len(result.latest_works) >= 3
        ids = [w["id"] for w in result.latest_works]
        assert "TEST-001" in ids
        assert "TEST-002" in ids
        assert "TEST-003" in ids

    async def test_javdb_works_merged_into_latest(self, svc):
        """JavDb works get merged with JavBus works (dedup by id)."""
        _mock_resolver_result(svc)
        _mock_javbus_latest(svc)
        _mock_wiki(svc)
        _mock_javdb_scraper(svc, works=[
            {"id": "TEST-001", "img": "https://javdb.com/jdb.jpg", "date": "2026-05-10"},
            {"id": "JAVDB-001", "img": "https://javdb.com/unique.jpg", "date": "2026-05-09"},
        ])

        result = await svc.query_profile_async("三上悠亜")
        ids = [w["id"] for w in result.latest_works]
        # TEST-001 from JavBus kept (already in dedup), JAVDB-001 added
        assert ids.count("TEST-001") == 1
        assert "JAVDB-001" in ids

    async def test_latest_works_sorted_by_date_desc(self, svc):
        """Works sorted newest first, empty dates at bottom."""
        _mock_resolver_result(svc)
        svc.javbus.get_new_ids_by_star_name = MagicMock(return_value=(200, ["A", "B", "C"]))
        svc._javbus_svc.build_latest_works = MagicMock(return_value=[
            {"id": "A", "date": "2026-04-01"},
            {"id": "B", "date": ""},
            {"id": "C", "date": "2026-05-01"},
        ])
        _mock_wiki(svc)
        _mock_javdb_scraper(svc, works=[])

        result = await svc.query_profile_async("test")
        dates = [w.get("date", "") for w in result.latest_works]
        # C (May) > A (Apr) > B (empty)
        assert dates == ["2026-05-01", "2026-04-01", ""]

    async def test_wiki_failure_does_not_block(self, svc):
        """Wiki failure → other data still returned."""
        _mock_resolver_result(svc)
        _mock_javbus_latest(svc)
        svc._wiki_svc.wiki_page_by_lang = MagicMock(side_effect=Exception("wiki timeout"))
        svc._wiki_svc.get_star_extra_info = MagicMock(side_effect=Exception("wiki extra timeout"))
        _mock_javdb_scraper(svc, works=[])

        result = await svc.query_profile_async("三上悠亜")
        assert result.found
        assert result.star_name == "三上悠亜"
        # latest_works still from JavBus
        assert len(result.latest_works) >= 1

    async def test_all_sources_fail_returns_found_profile(self, svc):
        """Resolver succeeds but all sources fail → still returns found profile with empty works."""
        _mock_resolver_result(svc)
        svc.javbus.get_new_ids_by_star_name = MagicMock(return_value=(404, []))
        svc._javbus_svc.build_latest_works = MagicMock(return_value=[])
        svc._wiki_svc.wiki_page_by_lang = MagicMock(side_effect=Exception("wiki fail"))
        svc._wiki_svc.get_star_extra_info = MagicMock(side_effect=Exception("extra fail"))
        svc._javdb_scraper.get_actress_works = AsyncMock(side_effect=Exception("javdb fail"))
        svc._javdb_scraper.search_actress = AsyncMock(side_effect=Exception("avatar fail"))

        result = await svc.query_profile_async("三上悠亜")
        assert result.found
        assert result.latest_works == []
        assert result.avatar_url is None

    async def test_cache_stores_result(self, svc):
        """After query, cache stores ActressProfile.__dict__."""
        _mock_resolver_result(svc)
        _mock_javbus_latest(svc)
        _mock_wiki(svc)
        _mock_javdb_scraper(svc, works=[])

        result = await svc.query_profile_async("三上悠亜")
        cache_key = ("profile", "三上悠亜", 5, 5)
        cached = svc.profile_cache.get(cache_key)
        assert cached is not None
        assert cached["star_name"] == "三上悠亜"

    async def test_subsequent_query_uses_cache(self, svc):
        """Second query does not call resolver (uses cache)."""
        _mock_resolver_result(svc)
        _mock_javbus_latest(svc)
        _mock_wiki(svc)
        _mock_javdb_scraper(svc, works=[])

        await svc.query_profile_async("三上悠亜")
        svc._resolver.resolve = MagicMock(side_effect=AssertionError("should be cached"))

        result = await svc.query_profile_async("三上悠亜")
        assert result.found
        assert result.star_name == "三上悠亜"

    async def test_different_names_different_cache_keys(self, svc):
        """Different names produce separate cache entries."""
        svc._resolver.resolve = MagicMock(return_value=("A", {"star_name": "Actress A", "star_id": "A-001"}, []))
        svc.javbus.get_new_ids_by_star_name = MagicMock(return_value=(200, []))
        svc._javbus_svc.build_latest_works = MagicMock(return_value=[])
        svc._wiki_svc.wiki_page_by_lang = MagicMock(return_value={})
        svc._wiki_svc.get_star_extra_info = MagicMock(return_value={})
        svc._javdb_scraper.get_actress_works = AsyncMock(return_value=[])
        svc._javdb_scraper.search_actress = AsyncMock(return_value=None)

        result_a = await svc.query_profile_async("Actress A")
        result_b = await svc.query_profile_async("Actress B")
        assert result_a.found
        assert result_b.found

    async def test_avatar_sets_avatar_url(self, svc):
        """search_actress avatar → ActressProfile.avatar_url."""
        _mock_resolver_result(svc)
        _mock_javbus_latest(svc, ids=[])
        _mock_wiki(svc)
        svc._javdb_scraper.get_actress_works = AsyncMock(return_value=[])
        svc._javdb_scraper.search_actress = AsyncMock(return_value={
            "name": "三上悠亜", "url": "https://javdb.com/abc", "avatar": "https://javdb.com/avatar.jpg",
        })

        result = await svc.query_profile_async("三上悠亜")
        assert result.avatar_url == "https://javdb.com/avatar.jpg"

    async def test_avatar_search_failure_returns_none(self, svc):
        """search_actress exception → avatar_url is None, other data ok."""
        _mock_resolver_result(svc)
        _mock_javbus_latest(svc, ids=[])
        _mock_wiki(svc)
        svc._javdb_scraper.get_actress_works = AsyncMock(return_value=[])
        svc._javdb_scraper.search_actress = AsyncMock(side_effect=Exception("cf block"))

        result = await svc.query_profile_async("三上悠亜")
        assert result.avatar_url is None
        assert result.found
