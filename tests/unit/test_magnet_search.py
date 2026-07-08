"""Tests for magnet_search: search_magnets, _search_variations, caching."""
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnError

from app.magnet_search import search_magnets, _do_search, _search_variations, _cache, _get_session


class TestDoSearch:
    """_do_search: HTTP request, HTML parsing."""

    @patch("app.magnet_search._get_session")
    def test_parse_results(self, mock_get_session):
        """Parse valid HTML → return magnet list."""
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
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_get_session.return_value = mock_session

        results = _do_search("test", limit=5, timeout=10)
        assert len(results) == 1
        assert results[0]["title"] == "Test Title"
        assert results[0]["magnet"] == "magnet:?xt=urn:btih:abc123"
        assert results[0]["size"] == "1.2 GiB"

    @patch("app.magnet_search._get_session")
    def test_no_results(self, mock_get_session):
        """Empty table → return empty list."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><table class='torrent-list'><tbody></tbody></table></body></html>"
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_get_session.return_value = mock_session

        results = _do_search("nonexistent", limit=5, timeout=10)
        assert results == []

    @patch("app.magnet_search._get_session")
    def test_http_error_returns_empty(self, mock_get_session):
        """Non-200 status → empty list."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_get_session.return_value = mock_session

        results = _do_search("test", limit=5, timeout=10)
        assert results == []

    @patch("app.magnet_search._get_session")
    def test_request_exception_returns_empty(self, mock_get_session):
        """Network error → empty list."""
        mock_session = MagicMock()
        mock_session.get.side_effect = RequestsConnError("connection error")
        mock_get_session.return_value = mock_session

        results = _do_search("test", limit=5, timeout=10)
        assert results == []


class TestSearchVariations:
    """_search_variations: fallback strategies."""

    @patch("app.magnet_search._do_search")
    def test_exact_query_first(self, mock_do_search):
        """Exact match → return immediately."""
        mock_do_search.return_value = [{"title": "Exact", "magnet": "magnet:1", "size": "1 GiB"}]
        results = _search_variations("MIZD-537", 5, 10)
        assert len(results) == 1
        assert results[0]["title"] == "Exact"
        mock_do_search.assert_called_once_with("MIZD-537", 5, 10)

    @patch("app.magnet_search._do_search")
    def test_fallback_remove_hyphen(self, mock_do_search):
        """No exact match → try without hyphen."""
        mock_do_search.side_effect = [
            [],  # exact: no results
            [{"title": "No Hyphen", "magnet": "magnet:2", "size": "1 GiB"}],  # no hyphen
        ]
        results = _search_variations("MIZD-537", 5, 10)
        assert len(results) == 1
        assert mock_do_search.call_count == 2
        mock_do_search.assert_any_call("MIZD-537", 5, 10)
        mock_do_search.assert_any_call("MIZD537", 5, 10)

    @patch("app.magnet_search._do_search")
    def test_fallback_prefix_only(self, mock_do_search):
        """No hyphen variant → try prefix only."""
        mock_do_search.side_effect = [
            [],  # exact
            [],  # no hyphen
            [{"title": "Prefix", "magnet": "magnet:3", "size": "1 GiB"}],  # prefix
        ]
        results = _search_variations("MIZD-537", 5, 10)
        assert len(results) == 1
        assert mock_do_search.call_count == 3
        mock_do_search.assert_any_call("MIZD", 5, 10)

    @patch("app.magnet_search._do_search")
    def test_fallback_numeric_part(self, mock_do_search):
        """All else fails → try numeric part."""
        mock_do_search.side_effect = [
            [],  # exact
            [],  # no hyphen
            [],  # prefix
            [{"title": "Number", "magnet": "magnet:4", "size": "1 GiB"}],  # numeric
        ]
        results = _search_variations("MIZD-537", 5, 10)
        assert len(results) == 1
        assert mock_do_search.call_count == 4
        mock_do_search.assert_any_call("537", 5, 10)

    @patch("app.magnet_search._do_search")
    def test_all_fallbacks_fail(self, mock_do_search):
        """All fail → return empty."""
        mock_do_search.return_value = []
        results = _search_variations("MIZD-537", 5, 10)
        assert results == []

    @patch("app.magnet_search._do_search")
    def test_no_hyphen_in_query(self, mock_do_search):
        """No hyphen → only one try."""
        mock_do_search.return_value = []
        results = _search_variations("MIZD537", 5, 10)
        mock_do_search.assert_called_once()
        assert results == []


class TestSearchMagnets:
    """search_magnets: public API, caching, input validation."""

    def setup_method(self):
        _cache.clear()

    @patch("app.magnet_search._search_variations")
    def test_cache_hit(self, mock_search_variations):
        """Cached result → return without calling search."""
        _cache.set(("test", 5), [{"title": "Cached", "magnet": "m:1", "size": "1 GiB"}])
        results = search_magnets("test", limit=5, timeout=10)
        assert len(results) == 1
        assert results[0]["title"] == "Cached"
        mock_search_variations.assert_not_called()

    @patch("app.magnet_search._search_variations")
    def test_cache_miss_calls_search(self, mock_search_variations):
        """No cache → call search."""
        mock_search_variations.return_value = [{"title": "Fresh", "magnet": "m:2", "size": "1 GiB"}]
        results = search_magnets("test", limit=5, timeout=10)
        assert len(results) == 1
        mock_search_variations.assert_called_once()

    @patch("app.magnet_search._search_variations")
    def test_empty_query_returns_empty(self, mock_search_variations):
        """Empty query → return empty."""
        assert search_magnets("") == []
        assert search_magnets("   ") == []
        mock_search_variations.assert_not_called()

    @patch("app.magnet_search._search_variations")
    def test_limit_clamping(self, mock_search_variations):
        """Limit clamped to [1, 10]."""
        mock_search_variations.return_value = []
        search_magnets("test", limit=999, timeout=10)
        args = mock_search_variations.call_args[0]
        # limit=10 (clamped), not 999
        assert args[1] == 10

    @patch("app.magnet_search._search_variations")
    def test_min_limit(self, mock_search_variations):
        """Limit clamped to 1 minimum."""
        mock_search_variations.return_value = []
        search_magnets("test", limit=0, timeout=10)
        args = mock_search_variations.call_args[0]
        assert args[1] == 1

    @patch("app.magnet_search._search_variations")
    def test_timeout_clamping(self, mock_search_variations):
        """Timeout clamped to [5, 60]."""
        mock_search_variations.return_value = []
        search_magnets("test", limit=5, timeout=999)
        args = mock_search_variations.call_args[0]
        assert args[2] == 60

    @patch("app.magnet_search._search_variations")
    def test_min_timeout(self, mock_search_variations):
        """Timeout clamped to 5 minimum."""
        mock_search_variations.return_value = []
        search_magnets("test", limit=5, timeout=1)
        args = mock_search_variations.call_args[0]
        assert args[2] == 5