"""Tests for ProfileResolver: name resolution, wiki aliases, fuzzy fallback."""
from unittest.mock import MagicMock

import pytest

from app.services.resolver import ProfileResolver
from app.services.text_utils import normalize_name, contains_cjk


class TestTextUtils:
    """text_utils: normalize_name, contains_cjk."""

    def test_normalize_name(self):
        assert normalize_name("  三上悠亜  ") == "三上悠亜"
        assert normalize_name("  TEST  ") == "TEST"

    def test_contains_cjk_true(self):
        assert contains_cjk("三上悠亜")
        assert contains_cjk("hello 世界")

    def test_contains_cjk_false(self):
        assert not contains_cjk("hello world")
        assert not contains_cjk("12345")


class TestProfileResolver:
    """ProfileResolver.resolve: exact match, fuzzy fallback, suggestions."""

    @pytest.fixture
    def resolver(self):
        name_match = MagicMock()
        name_match.name_candidates.return_value = ["TestActress"]
        name_match.find_star.return_value = ("TestActress", {"star_name": "TestActress", "star_id": "TA-001"})
        wiki = MagicMock()
        wiki.wiki_aliases.return_value = []
        javbus = MagicMock()
        javbus.fuzzy_search_stars.return_value = (200, [])
        limiter = MagicMock()
        return ProfileResolver(
            name_match_svc=name_match,
            wiki_svc=wiki,
            javbus=javbus,
            javbus_limiter=limiter,
        )

    def test_resolve_exact_match(self, resolver):
        """Exact match → returns star."""
        matched_name, star, suggestions = resolver.resolve("TestActress")
        assert matched_name == "TestActress"
        assert star is not None
        assert star["star_name"] == "TestActress"
        assert suggestions == []

    def test_no_match_returns_suggestions(self, resolver):
        """No match → returns suggestions."""
        resolver._name_match_svc.find_star.return_value = (None, None)
        resolver.javbus.fuzzy_search_stars.return_value = (200, ["Suggestion A", "Suggestion B"])
        matched_name, star, suggestions = resolver.resolve("Unknown")
        assert star is None
        assert len(suggestions) >= 1

    def test_wiki_aliases_expand_candidates(self, resolver):
        """Wiki aliases expand candidate list."""
        resolver._name_match_svc.name_candidates.return_value = ["Name"]
        resolver._name_match_svc.find_star.side_effect = [
            (None, None),  # first call: no match
            ("AliasName", {"star_name": "AliasName", "star_id": "AN-001"}),  # second call: match
        ]
        resolver._wiki_svc.wiki_aliases.return_value = ["AliasName"]
        matched_name, star, suggestions = resolver.resolve("Name")
        assert star is not None
        assert star["star_name"] == "AliasName"

    def test_no_suggestions_when_none_found(self, resolver):
        """No fuzzy matches → empty suggestions."""
        resolver._name_match_svc.find_star.return_value = (None, None)
        resolver.javbus.fuzzy_search_stars.return_value = (404, [])
        matched_name, star, suggestions = resolver.resolve("TotallyUnknown")
        assert star is None
        assert suggestions == []

    def test_suggestions_capped_at_10(self, resolver):
        """Suggestions capped at 10."""
        resolver._name_match_svc.find_star.return_value = (None, None)
        resolver.javbus.fuzzy_search_stars.return_value = (200, [f"Suggestion {i}" for i in range(20)])
        matched_name, star, suggestions = resolver.resolve("Unknown")
        assert len(suggestions) <= 10

    def test_resolve_with_aliases(self, resolver):
        """Alias map lookup works."""
        resolver._name_match_svc.name_candidates.return_value = ["三上悠亜", "三上悠亚"]
        resolver._name_match_svc.find_star.return_value = ("三上悠亜", {"star_name": "三上悠亜", "star_id": "YM-001"})
        matched_name, star, suggestions = resolver.resolve("三上悠亚")
        assert star is not None
        assert star["star_name"] == "三上悠亜"