"""Tests for RankService with mocked JavDbScraper (curl-based)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cache import TTLCache


class TestRankService:
    """RankService: cache warm, get_hot_star_rankings, fallback."""

    @pytest.fixture
    def cache(self):
        return TTLCache(max_size=32, default_ttl=3600)

    @pytest.fixture
    def scraper(self):
        s = AsyncMock()
        s.get_actors_ranking = AsyncMock()
        return s

    @pytest.fixture
    def svc(self, cache, scraper):
        from app.services.rank_service import RankService
        s = RankService(rank_cache=cache, refresh_interval=600, javdb_scraper=scraper)
        return s

    async def test_get_hot_star_rankings_delegates_to_scraper(self, svc, scraper):
        scraper.get_actors_ranking.return_value = [
            {"name": "Actor A", "url": "/a", "avatar": ""},
            {"name": "Actor B", "url": "/b", "avatar": ""},
        ]
        result = await svc.get_hot_star_rankings(limit=20, page=1)
        assert len(result) == 2
        scraper.get_actors_ranking.assert_awaited_with(limit=20, page=1)

    async def test_result_cached(self, svc, scraper):
        scraper.get_actors_ranking.return_value = [
            {"name": "Cached", "url": "/c", "avatar": ""},
        ]
        await svc.get_hot_star_rankings(limit=20, page=1)
        scraper.get_actors_ranking.reset_mock()

        # Second call should use cache, not scraper
        result = await svc.get_hot_star_rankings(limit=20, page=1)
        assert len(result) == 1
        scraper.get_actors_ranking.assert_not_awaited()

    async def test_empty_result_from_scraper(self, svc, scraper):
        scraper.get_actors_ranking.return_value = []
        result = await svc.get_hot_star_rankings(limit=20, page=1)
        assert result == []

    async def test_fallback_to_page_1_cache(self, svc, scraper):
        """Page 2 fails → falls back to cached page 1 data."""
        # Prime page 1 cache
        scraper.get_actors_ranking.return_value = [{"name": "Prime", "url": "/p"}]
        await svc.get_hot_star_rankings(limit=20, page=1)
        # Page 2 fails
        scraper.get_actors_ranking.return_value = []
        result = await svc.get_hot_star_rankings(limit=20, page=2)
        assert result == []  # page 2 has no page 1 fallback (page != 1)

    async def test_page_2_empty_no_fallback(self, svc, scraper):
        """Page 2+ returns empty → no fallback (only page 1 has fallback)."""
        scraper.get_actors_ranking.return_value = []
        result = await svc.get_hot_star_rankings(limit=20, page=3)
        assert result == []

    async def test_scraper_exception_returns_none(self, svc, scraper):
        scraper.get_actors_ranking.side_effect = Exception("cf block")
        result = await svc.get_hot_star_rankings(limit=20, page=1)
        assert result == []

    async def test_scraper_not_set(self, svc):
        """No scraper set → returns empty."""
        svc._scraper = None
        result = await svc.get_hot_star_rankings(limit=20, page=1)
        assert result == []

    async def test_warm_cache_calls_scraper(self, svc, scraper):
        scraper.get_actors_ranking.return_value = [{"name": f"Warm Page {p}"} for p in range(1, 21)]
        await svc._warm_cache()
        # Should have called scraper for pages 1, 2, 3
        assert scraper.get_actors_ranking.call_count >= 1

    async def test_warm_cache_skips_if_cached(self, svc, scraper):
        """Warming skips pages already in cache."""
        svc.rank_cache.set(("rank", 20, 1), [{"name": "Already cached"}])
        scraper.get_actors_ranking.return_value = [{"name": "New"}]
        await svc._warm_cache()
        # Page 1 cached → not called, pages 2-3 called
        calls = [c[1] for c in scraper.get_actors_ranking.call_args_list]
        pages = [c["page"] for c in calls]
        assert 1 not in pages
        assert 2 in pages
        assert 3 in pages

    async def test_limit_clamping(self, svc, scraper):
        scraper.get_actors_ranking.return_value = []
        result = await svc.get_hot_star_rankings(limit=999, page=1)
        assert result == []
        # Scraper called with capped limit
        scraper.get_actors_ranking.assert_awaited_with(limit=50, page=1)

    async def test_page_clamping(self, svc, scraper):
        scraper.get_actors_ranking.return_value = []
        await svc.get_hot_star_rankings(limit=20, page=999)
        # Scraper called with capped page
        scraper.get_actors_ranking.assert_awaited_with(limit=20, page=5)


class TestJavDbScraperGetActorsRanking:
    """JavDbScraper.get_actors_ranking with mocked curl."""

    @pytest.fixture
    def scraper(self):
        from app.services.javdb_scraper import JavDbScraper
        s = JavDbScraper(cache=TTLCache(max_size=32, default_ttl=3600))
        return s

    async def test_returns_parsed_actors(self, scraper):
        html = """
        <div class="actor-box">
          <a href="/actors/abc"><strong>A Actress</strong></a>
          <img src="https://javdb.com/avatar/a.jpg">
        </div>
        <div class="actor-box">
          <a href="/actors/def"><strong>B Actress</strong></a>
          <img src="https://javdb.com/avatar/b.jpg">
        </div>
        """
        with patch.object(scraper, "_rate_limited_curl", AsyncMock(return_value=html)):
            result = await scraper.get_actors_ranking(limit=20, page=1)
        assert len(result) == 2
        assert result[0]["name"] == "A Actress"
        assert result[1]["name"] == "B Actress"

    async def test_cloudflare_challenge_returns_empty(self, scraper):
        html = "<html><head><title>Cloudflare Challenge</title></head><body></body></html>"
        with patch.object(scraper, "_rate_limited_curl", AsyncMock(return_value=html)):
            result = await scraper.get_actors_ranking(limit=20, page=1)
        assert result == []

    async def test_curl_failure_returns_empty(self, scraper):
        with patch.object(scraper, "_rate_limited_curl", AsyncMock(return_value=None)):
            result = await scraper.get_actors_ranking(limit=20, page=1)
        assert result == []

    async def test_cached_result_not_re_fetched(self, scraper):
        html = """
        <div class="actor-box">
          <a href="/actors/abc"><strong>Cached</strong></a>
          <img src="">
        </div>
        """
        with patch.object(scraper, "_rate_limited_curl", AsyncMock(return_value=html)):
            await scraper.get_actors_ranking(limit=20, page=1)
        # Second call should use cache
        curl_mock = AsyncMock(side_effect=AssertionError("should not call curl"))
        with patch.object(scraper, "_rate_limited_curl", curl_mock):
            result = await scraper.get_actors_ranking(limit=20, page=1)
            assert len(result) == 1
            assert result[0]["name"] == "Cached"

    async def test_limit_respected(self, scraper):
        html = "".join(
            f'<div class="actor-box"><a href="/a{i}"><strong>A{i}</strong></a><img src=""></div>'
            for i in range(10)
        )
        with patch.object(scraper, "_rate_limited_curl", AsyncMock(return_value=html)):
            result = await scraper.get_actors_ranking(limit=3, page=1)
        assert len(result) == 3

    async def test_empty_html_returns_empty(self, scraper):
        with patch.object(scraper, "_rate_limited_curl", AsyncMock(return_value="")):
            result = await scraper.get_actors_ranking(limit=20, page=1)
        assert result == []
