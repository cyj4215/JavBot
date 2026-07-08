"""Tests for WikiService: Wikipedia/Wikidata info extraction."""
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import requests

from app.cache import TTLCache
from app.rate_limiter import RateLimiter


# ── Helper: build a WikiService with fully mocked dependencies ──

def _make_svc(http_session=None, cache=None):
    """Create WikiService with all dependencies mocked."""
    from app.services.wiki_service import WikiService
    if http_session is None:
        http_session = MagicMock(spec=requests.Session)
    if cache is None:
        cache = TTLCache(max_size=128, default_ttl=3600)
    limiter = RateLimiter(calls_per_second=100)  # fast for tests
    return WikiService(
        proxy_addr="",
        wiki_user_agent="test-agent/1.0",
        http_session=http_session,
        wiki_page_cache=cache,
        wiki_limiter=limiter,
    )


def _mock_wiki_page(title="三上悠亜", fullurl="https://zh.wikipedia.org/wiki/三上悠亜", exists=True, langlinks=None):
    """Create a mock wikipediaapi page object."""
    page = MagicMock()
    page.title = title
    page.fullurl = fullurl
    page.exists.return_value = exists
    if langlinks is not None:
        page.langlinks = langlinks
    else:
        page.langlinks = {}
    return page


# ── Pure static method tests ──

class TestFormatWikidataTime:
    """_format_wikidata_time: Wikidata timestamp → YYYY-MM-DD."""

    def test_standard_format(self):
        from app.services.wiki_service import WikiService
        result = WikiService._format_wikidata_time("+1993-08-19T00:00:00Z")
        assert result == "1993-08-19"

    def test_negative_century_ignored(self):
        from app.services.wiki_service import WikiService
        result = WikiService._format_wikidata_time("-1900-01-01T00:00:00Z")
        assert result == "1900-01-01"

    def test_empty_string(self):
        from app.services.wiki_service import WikiService
        assert WikiService._format_wikidata_time("") == ""

    def test_none_input(self):
        from app.services.wiki_service import WikiService
        assert WikiService._format_wikidata_time(None) == ""


class TestCleanWikiText:
    """_clean_wiki_text: strip brackets, normalize whitespace."""

    def test_removes_brackets(self):
        from app.services.wiki_service import WikiService
        result = WikiService._clean_wiki_text("hello [1] world")
        assert result == "hello world"

    def test_normalizes_whitespace(self):
        from app.services.wiki_service import WikiService
        result = WikiService._clean_wiki_text("  hello   world  ")
        assert result == "hello world"

    def test_empty_string(self):
        from app.services.wiki_service import WikiService
        assert WikiService._clean_wiki_text("") == ""


# ── _extract_wikidata_entity_id ──

class TestExtractWikidataEntityId:
    """_extract_wikidata_entity_id: Wikipedia API → Q-ID."""

    def test_returns_qid(self):
        """Valid response → returns Q-ID."""
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.json.return_value = {
            "query": {"pages": {"123": {"pageprops": {"wikibase_item": "Q12345"}}}}
        }
        svc = _make_svc(http_session=http)
        qid = svc._extract_wikidata_entity_id("https://zh.wikipedia.org/wiki/三上悠亜")
        assert qid == "Q12345"

    def test_no_wikibase_item(self):
        """Response without wikibase_item → empty string."""
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.json.return_value = {
            "query": {"pages": {"123": {"pageprops": {}}}}
        }
        svc = _make_svc(http_session=http)
        qid = svc._extract_wikidata_entity_id("https://zh.wikipedia.org/wiki/Test")
        assert qid == ""

    def test_http_error_returns_empty(self):
        """HTTP error → empty string."""
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 500
        svc = _make_svc(http_session=http)
        qid = svc._extract_wikidata_entity_id("https://zh.wikipedia.org/wiki/Test")
        assert qid == ""

    def test_exception_returns_empty(self):
        """Exception → empty string."""
        http = MagicMock(spec=requests.Session)
        http.get.side_effect = Exception("network error")
        svc = _make_svc(http_session=http)
        qid = svc._extract_wikidata_entity_id("https://zh.wikipedia.org/wiki/Test")
        assert qid == ""


# ── _extract_info_from_wikipedia ──

class TestExtractInfoFromWikipedia:
    """_extract_info_from_wikipedia: infobox HTML → birth_date, height, etc."""

    def _make_infobox_html(self, rows: str) -> str:
        return f"""<html><body><table class="infobox">{rows}</table></body></html>"""

    def test_extracts_birth_date(self):
        """infobox with birth date → parsed."""
        html = self._make_infobox_html("""
            <tr><th>出生</th><td>1993年8月19日</td></tr>
        """)
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.text = html
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikipedia("https://zh.wikipedia.org/wiki/三上悠亜")
        assert info["birth_date"] == "1993-08-19"

    def test_extracts_birth_date_japanese(self):
        """Japanese infobox format → parsed."""
        html = self._make_infobox_html("""
            <tr><th>生年月日</th><td>1993年8月19日</td></tr>
        """)
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.text = html
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikipedia("https://ja.wikipedia.org/wiki/Test")
        assert info["birth_date"] == "1993-08-19"

    def test_extracts_height(self):
        """infobox with height → parsed."""
        html = self._make_infobox_html("""
            <tr><th>身長</th><td>160 cm</td></tr>
        """)
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.text = html
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikipedia("https://ja.wikipedia.org/wiki/Test")
        assert "160" in info["height"]

    def test_extracts_measurements(self):
        """infobox with measurements → parsed."""
        html = self._make_infobox_html("""
            <tr><th>スリーサイズ</th><td>88 - 58 - 88 cm</td></tr>
        """)
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.text = html
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikipedia("https://ja.wikipedia.org/wiki/Test")
        assert info["measurements"] == "88 - 58 - 88 cm"

    def test_extracts_cup(self):
        """infobox with cup → parsed."""
        html = self._make_infobox_html("""
            <tr><th>カップ</th><td>E</td></tr>
        """)
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.text = html
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikipedia("https://ja.wikipedia.org/wiki/Test")
        assert info["cup"] == "E"

    def test_social_links_extracted(self):
        """Infobox with social media links → extracted."""
        html = self._make_infobox_html("""
            <tr><th>别的</th><td>
                <a href="https://twitter.com/test_actress">Twitter</a>
                <a href="https://www.instagram.com/test_actress">Instagram</a>
            </td></tr>
        """)
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.text = html
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikipedia("https://zh.wikipedia.org/wiki/Test")
        assert len(info["socials"]) >= 1
        urls = [s["url"] for s in info["socials"]]
        assert any("twitter.com" in u for u in urls)

    def test_no_infobox_returns_empty(self):
        """Page without infobox → empty info."""
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.text = "<html><body>No infobox here</body></html>"
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikipedia("https://zh.wikipedia.org/wiki/Test")
        assert info["birth_date"] == ""
        assert info["height"] == ""

    def test_http_error_returns_empty(self):
        """HTTP error → empty info."""
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 404
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikipedia("https://zh.wikipedia.org/wiki/Test")
        assert info["birth_date"] == ""


# ── _extract_info_from_wikidata ──

class TestExtractInfoFromWikidata:
    """_extract_info_from_wikidata: Wikidata JSON → birth_date, height, socials."""

    def _make_wikidata_json(self, entity_id="Q12345", claims=None):
        return {
            "entities": {
                entity_id: {
                    "id": entity_id,
                    "claims": claims or {},
                }
            }
        }

    def test_birth_date_from_wikidata(self):
        """Wikidata P569 (birth date) → extracted."""
        http = MagicMock(spec=requests.Session)
        # _extract_wikidata_entity_id
        http.get.return_value.status_code = 200
        http.get.return_value.json.return_value = {
            "query": {"pages": {"123": {"pageprops": {"wikibase_item": "Q12345"}}}}
        }
        # Wikidata response for second call
        http.get.return_value.json.side_effect = [
            {"query": {"pages": {"123": {"pageprops": {"wikibase_item": "Q12345"}}}}},
            self._make_wikidata_json(claims={
                "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1993-08-19T00:00:00Z"}}}}],
            }),
        ]
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikidata("https://zh.wikipedia.org/wiki/Test")
        assert info["birth_date"] == "1993-08-19"

    def test_height_from_wikidata(self):
        """Wikidata P2048 (height in meters) → converted to cm."""
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.json.side_effect = [
            {"query": {"pages": {"123": {"pageprops": {"wikibase_item": "Q12345"}}}}},
            self._make_wikidata_json(claims={
                "P2048": [{"mainsnak": {"datavalue": {"value": {"amount": "1.6", "unit": "http://www.wikidata.org/entity/Q11573"}}}}],
            }),
        ]
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikidata("https://zh.wikipedia.org/wiki/Test")
        assert "160" in info["height"]

    def test_no_claims_returns_empty(self):
        """Entity without claims → empty info."""
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.json.side_effect = [
            {"query": {"pages": {"123": {"pageprops": {"wikibase_item": "Q12345"}}}}},
            {"entities": {"Q12345": {"id": "Q12345", "claims": {}}}},
        ]
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikidata("https://zh.wikipedia.org/wiki/Test")
        assert info["birth_date"] == ""

    def test_no_entity_id_returns_empty(self):
        """No wikibase item → empty info."""
        http = MagicMock(spec=requests.Session)
        http.get.return_value.status_code = 200
        http.get.return_value.json.return_value = {
            "query": {"pages": {"123": {"pageprops": {}}}}
        }
        svc = _make_svc(http_session=http)
        info = svc._extract_info_from_wikidata("https://zh.wikipedia.org/wiki/Test")
        assert info == {"birth_date": "", "height": "", "measurements": "", "cup": "", "socials": []}


# ── wiki_page_by_lang ──

class TestWikiPageByLang:
    """wiki_page_by_lang: Wikipedia lookup with langlinks."""

    @pytest.fixture(autouse=True)
    def _patch_wikipedia(self, monkeypatch):
        """Mock wikipediaapi at module level."""
        import app.services.wiki_service as ws
        self._wiki_instance = MagicMock()
        monkeypatch.setattr(ws.wikipediaapi, "Wikipedia", lambda language, user_agent: self._wiki_instance)

    def test_page_exists_with_langlink(self):
        """Found page with target language link → returns linked page info."""
        linked_page = MagicMock()
        linked_page.title = "Mikami Yua"
        linked_page.fullurl = "https://en.wikipedia.org/wiki/Mikami_Yua"
        linked_page.language = "en"
        self._wiki_instance.page.return_value = _mock_wiki_page(
            title="三上悠亜",
            fullurl="https://zh.wikipedia.org/wiki/三上悠亜",
            langlinks={"en": linked_page},
        )
        svc = _make_svc()
        result = svc.wiki_page_by_lang("三上悠亜", from_lang="zh", to_lang="en")
        assert result["title"] == "Mikami Yua"
        assert result["url"] == "https://en.wikipedia.org/wiki/Mikami_Yua"
        assert result["lang"] == "en"

    def test_page_exists_no_langlink(self):
        """Found page without target lang → returns original page."""
        self._wiki_instance.page.return_value = _mock_wiki_page(
            title="三上悠亜",
            fullurl="https://zh.wikipedia.org/wiki/三上悠亜",
        )
        svc = _make_svc()
        result = svc.wiki_page_by_lang("三上悠亜", from_lang="zh", to_lang="en")
        assert result["title"] == "三上悠亜"
        assert result["lang"] == "zh"

    def test_page_not_exists(self):
        """Non-existent page → empty dict."""
        page = MagicMock()
        page.exists.return_value = False
        self._wiki_instance.page.return_value = page
        svc = _make_svc()
        result = svc.wiki_page_by_lang("NonExistent", from_lang="en", to_lang="zh")
        assert result == {}

    def test_exception_returns_empty(self):
        """Wikipedia API exception → empty dict."""
        self._wiki_instance.page.side_effect = Exception("API error")
        svc = _make_svc()
        result = svc.wiki_page_by_lang("Error", from_lang="en", to_lang="zh")
        assert result == {}

    def test_cache_hit(self):
        """Cached result → no Wikipedia API call."""
        svc = _make_svc()
        svc.wiki_page_cache.set(("wiki_page", "三上悠亜", "zh", "en"), {"title": "Cached"})
        self._wiki_instance.page.side_effect = AssertionError("should not call Wikipedia")
        result = svc.wiki_page_by_lang("三上悠亜", from_lang="zh", to_lang="en")
        assert result["title"] == "Cached"


# ── wiki_aliases ──

class TestWikiAliases:
    """wiki_aliases: cross-language alias lookup."""

    @pytest.fixture(autouse=True)
    def _patch_wikipedia(self, monkeypatch):
        import app.services.wiki_service as ws
        self._wiki_instance = MagicMock()
        monkeypatch.setattr(ws.wikipediaapi, "Wikipedia", lambda language, user_agent: self._wiki_instance)

    def test_cjk_name_searches_zh(self):
        """CJK name → searches zh→ja and zh→en."""
        self._wiki_instance.page.return_value = _mock_wiki_page(
            title="三上悠亜", fullurl="https://zh.wikipedia.org/wiki/三上悠亜",
        )
        svc = _make_svc()
        aliases = svc.wiki_aliases("三上悠亜")
        assert "三上悠亜" in aliases

    def test_non_cjk_name_searches_en(self):
        """Non-CJK name → searches en→ja."""
        self._wiki_instance.page.return_value = _mock_wiki_page(
            title="Yua Mikami", fullurl="https://en.wikipedia.org/wiki/Yua_Mikami",
        )
        svc = _make_svc()
        aliases = svc.wiki_aliases("Yua Mikami")
        assert "Yua Mikami" in aliases

    def test_no_duplicates(self):
        """Same alias from multiple sources → deduplicated."""
        page = _mock_wiki_page(
            title="三上悠亜", fullurl="https://zh.wikipedia.org/wiki/三上悠亜",
            langlinks={"en": MagicMock(title="Yua Mikami")},
        )
        self._wiki_instance.page.return_value = page
        svc = _make_svc()
        aliases = svc.wiki_aliases("三上悠亜")
        assert len(aliases) == len(set(aliases))


# ── get_star_extra_info ──

class TestGetStarExtraInfo:
    """get_star_extra_info: merges Wikipedia + Wikidata."""

    def test_merges_both_sources(self):
        """Wikipedia and Wikidata data merged."""
        http = MagicMock(spec=requests.Session)
        # _extract_wikidata_entity_id → Q-ID
        # Wikidata response
        http.get.return_value.status_code = 200
        http.get.return_value.json.side_effect = [
            {"query": {"pages": {"123": {"pageprops": {"wikibase_item": "Q12345"}}}}},
            {"entities": {"Q12345": {"claims": {}}}},
        ]
        svc = _make_svc(http_session=http)
        info = svc.get_star_extra_info("https://zh.wikipedia.org/wiki/三上悠亜")
        assert isinstance(info, dict)
        assert "birth_date" in info
        assert "height" in info
        assert "socials" in info

    def test_empty_url_returns_defaults(self):
        """Empty wiki_url → default empty dict."""
        svc = _make_svc()
        info = svc.get_star_extra_info("")
        assert info == {"birth_date": "", "height": "", "measurements": "", "cup": "", "socials": []}