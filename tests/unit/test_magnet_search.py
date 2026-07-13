"""Tests for MagnetSearch: search, _do_search, _search_variations, caching."""
from unittest.mock import MagicMock, patch

import pytest
import httpx

from app.magnet_search import MagnetSearch
from app.models.magnets import MagnetLink


@pytest.fixture
def ms():
    """Fresh MagnetSearch instance for each test."""
    return MagnetSearch()


class TestDoSearch:
    """_do_search: HTTP request, HTML parsing."""

    @patch("httpx.get")
    def test_parse_results(self, mock_get):
        """Parse valid HTML → return MagnetLink list."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """
        <table class="torrent-list">
          <tbody>
            <tr>
              <td></td>
              <td><a href="/view/1" class="comments">comment</a><a href="/view/1" title="Test Title">Test Title</a></td>
              <td></td>
              <td>1.2 GiB</td>
              <td></td>
              <td><a href="magnet:?xt=urn:btih:abc123">Magnet</a></td>
            </tr>
          </tbody>
        </table>
        """
        mock_get.return_value = mock_resp

        ms_instance = MagnetSearch()
        results = ms_instance._do_search("test", limit=5, timeout=10)
        assert len(results) == 1
        assert results[0].title == "Test Title"
        assert results[0].magnet == "magnet:?xt=urn:btih:abc123"
        assert results[0].size == "1.2 GiB"

    @patch("httpx.get")
    def test_no_results(self, mock_get):
        """Empty table → return empty list."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><table class='torrent-list'><tbody></tbody></table></body></html>"
        mock_get.return_value = mock_resp

        results = MagnetSearch()._do_search("nonexistent", limit=5, timeout=10)
        assert results == []

    @patch("httpx.get")
    def test_http_error_returns_empty(self, mock_get):
        """Non-200 status → empty list."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        results = MagnetSearch()._do_search("test", limit=5, timeout=10)
        assert results == []

    @patch("httpx.get")
    def test_request_exception_returns_empty(self, mock_get):
        """Network error → empty list."""
        mock_get.side_effect = httpx.RequestError("connection error")

        results = MagnetSearch()._do_search("test", limit=5, timeout=10)
        assert results == []


class TestSearchVariations:
    """_search_variations: fallback strategies."""

    def test_exact_query_first(self, ms):
        """Exact match → return immediately."""
        ms._do_search = MagicMock(return_value=[MagnetLink(title="Exact", magnet="magnet:1", size="1 GiB")])
        results = ms._search_variations("MIZD-537", 5, 10)
        assert len(results) == 1
        assert results[0].title == "Exact"
        ms._do_search.assert_called_once_with("MIZD-537", 5, 10)

    def test_fallback_remove_hyphen(self, ms):
        """No exact match → try without hyphen."""
        ms._do_search = MagicMock(side_effect=[
            [],
            [MagnetLink(title="No Hyphen", magnet="magnet:2", size="1 GiB")],
        ])
        results = ms._search_variations("MIZD-537", 5, 10)
        assert len(results) == 1
        assert results[0].title == "No Hyphen"
        assert ms._do_search.call_count == 2
        ms._do_search.assert_any_call("MIZD-537", 5, 10)
        ms._do_search.assert_any_call("MIZD537", 5, 10)

    def test_fallback_prefix_only(self, ms):
        """No hyphen variant → try prefix only."""
        ms._do_search = MagicMock(side_effect=[
            [], [],
            [MagnetLink(title="Prefix", magnet="magnet:3", size="1 GiB")],
        ])
        results = ms._search_variations("MIZD-537", 5, 10)
        assert len(results) == 1
        assert results[0].title == "Prefix"
        assert ms._do_search.call_count == 3
        ms._do_search.assert_any_call("MIZD", 5, 10)

    def test_fallback_numeric_part(self, ms):
        """All else fails → try numeric part."""
        ms._do_search = MagicMock(side_effect=[
            [], [], [],
            [MagnetLink(title="Number", magnet="magnet:4", size="1 GiB")],
        ])
        results = ms._search_variations("MIZD-537", 5, 10)
        assert len(results) == 1
        assert results[0].title == "Number"
        assert ms._do_search.call_count == 4
        ms._do_search.assert_any_call("537", 5, 10)

    def test_all_fallbacks_fail(self, ms):
        """All fail → return empty."""
        ms._do_search = MagicMock(return_value=[])
        results = ms._search_variations("MIZD-537", 5, 10)
        assert results == []

    def test_no_hyphen_in_query(self, ms):
        """No hyphen → only one try."""
        ms._do_search = MagicMock(return_value=[])
        results = ms._search_variations("MIZD537", 5, 10)
        ms._do_search.assert_called_once()
        assert results == []


class TestSearch:
    """search: public API, caching, input validation."""

    def test_cache_hit(self, ms):
        """Cached result → return without calling _search_variations."""
        ms._cache.set(("test", 5), [MagnetLink(title="Cached", magnet="m:1", size="1 GiB").model_dump(mode='json')])
        ms._search_variations = MagicMock()  # noqa
        results = ms.search("test", limit=5, timeout=10)
        assert len(results) == 1
        assert results[0].title == "Cached"

    def test_cache_miss_calls_search(self, ms):
        """No cache → call search."""
        ms._search_variations = MagicMock(  # noqa
            return_value=[MagnetLink(title="Fresh", magnet="m:2", size="1 GiB")]
        )
        results = ms.search("test", limit=5, timeout=10)
        assert len(results) == 1
        assert results[0].title == "Fresh"

    def test_empty_query_returns_empty(self, ms):
        """Empty query → return empty."""
        assert ms.search("") == []
        assert ms.search("   ") == []

    def test_limit_clamping(self, ms):
        """Limit clamped to [1, 10]."""
        ms._search_variations = MagicMock(return_value=[])  # noqa
        ms.search("test", limit=999, timeout=10)
        args = ms._search_variations.call_args[0]
        assert args[1] == 10

    def test_min_limit(self, ms):
        """Limit clamped to 1 minimum."""
        ms._search_variations = MagicMock(return_value=[])  # noqa
        ms.search("test", limit=0, timeout=10)
        args = ms._search_variations.call_args[0]
        assert args[1] == 1

    def test_timeout_clamping(self, ms):
        """Timeout clamped to [5, 60]."""
        ms._search_variations = MagicMock(return_value=[])  # noqa
        ms.search("test", limit=5, timeout=999)
        args = ms._search_variations.call_args[0]
        assert args[2] == 60

    def test_min_timeout(self, ms):
        """Timeout clamped to 5 minimum."""
        ms._search_variations = MagicMock(return_value=[])  # noqa
        ms.search("test", limit=5, timeout=1)
        args = ms._search_variations.call_args[0]
        assert args[2] == 5
