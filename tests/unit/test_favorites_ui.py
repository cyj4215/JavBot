"""Unit tests for favorites UI helpers (_time_ago, _sort_favorites, _render_favorites_page).

Pure functions — no DB or Telegram API required.
"""
from datetime import datetime, timedelta

import pytest
from telegram import InlineKeyboardMarkup

from app.handlers.favorites import _time_ago, _sort_favorites, _render_favorites_page


def _iso_now():
    return datetime.now().isoformat(timespec="seconds")


def _iso_minutes_ago(n):
    return (datetime.now() - timedelta(minutes=n)).isoformat(timespec="seconds")


def _iso_days_ago(n):
    return (datetime.now() - timedelta(days=n)).isoformat(timespec="seconds")


class TestTimeAgo:
    def test_empty(self):
        assert _time_ago("") == ""

    def test_just_now(self):
        ts = _iso_now()
        assert _time_ago(ts) == "刚刚"

    def test_minutes_ago(self):
        ts = _iso_minutes_ago(5)
        assert _time_ago(ts) == "5分钟前"

    def test_hours_ago(self):
        ts = _iso_minutes_ago(180)
        assert _time_ago(ts) == "3小时前"

    def test_days_ago(self):
        ts = _iso_days_ago(3)
        assert _time_ago(ts) == "3天前"

    def test_months_ago(self):
        ts = _iso_days_ago(45)
        assert _time_ago(ts) == "1月前"

    def test_invalid_format(self):
        assert _time_ago("not-a-date") == "not-a-date"


class TestSortFavorites:
    @pytest.fixture
    def favs(self):
        return [
            {"actress_name": "B Actress", "actress_id": "BBB-001", "created_at": "2026-03-01 10:00:00"},
            {"actress_name": "A Actress", "actress_id": "AAA-999", "created_at": "2026-01-15 08:00:00"},
            {"actress_name": "C Actress", "actress_id": "CCC-123", "created_at": "2026-02-20 12:00:00"},
        ]

    @pytest.fixture
    def query_map(self):
        return {
            "B Actress": "2026-05-10 15:00:00",
            "A Actress": "2026-04-01 10:00:00",
        }

    def test_sort_by_name(self, favs, query_map):
        result = _sort_favorites(favs, "name", query_map)
        names = [f["actress_name"] for f in result]
        assert names == ["A Actress", "B Actress", "C Actress"]

    def test_sort_by_date(self, favs, query_map):
        result = _sort_favorites(favs, "date", query_map)
        names = [f["actress_name"] for f in result]
        # Created_at desc: B (Mar), C (Feb), A (Jan)
        assert names == ["B Actress", "C Actress", "A Actress"]

    def test_sort_by_recent(self, favs, query_map):
        result = _sort_favorites(favs, "recent", query_map)
        names = [f["actress_name"] for f in result]
        # Recent desc: B (May 10), A (Apr 10), C (never queried → last)
        assert names == ["B Actress", "A Actress", "C Actress"]

    def test_sort_invalid_fallback_to_date(self, favs, query_map):
        result = _sort_favorites(favs, "invalid", query_map)
        names = [f["actress_name"] for f in result]
        assert names == ["B Actress", "C Actress", "A Actress"]


class TestRenderFavoritesPage:
    def _make_fav(self, name, actress_id="", created_at="2026-05-01 10:00:00"):
        return {"actress_name": name, "actress_id": actress_id, "created_at": created_at}

    def test_empty_favorites(self):
        """Single empty page still renders header."""
        text, markup = _render_favorites_page([], 1, 10, sort="date")
        assert "📚" in text
        assert "0 位" in text
        assert markup is not None
        # Nav row with sort button always present
        assert len(markup.inline_keyboard) >= 1

    def test_single_page(self):
        favs = [self._make_fav("三上悠亜", "SSIS-123"), self._make_fav("河北彩花", "SSIS-999")]
        text, markup = _render_favorites_page(favs, 1, 10, sort="date")
        assert "三上悠亜" in text
        assert "河北彩花" in text
        assert "🆔" in text
        assert "2 位" in text
        # 2 actress buttons + 1 nav row + 1 action row
        keyboard = markup.inline_keyboard
        assert len(keyboard) >= 2

    def test_pagination(self):
        favs = [self._make_fav(f"Actress {i}") for i in range(25)]
        text, markup = _render_favorites_page(favs, 1, 10, sort="date")
        assert "第 1/3 页" in text
        assert "25 位" in text
        keyboard = markup.inline_keyboard
        # At least: one row of buttons + nav (◀️ + ↕️sort + ▶️) + action
        assert len(keyboard) >= 2

    def test_page_2(self):
        favs = [self._make_fav(f"Actress {i}") for i in range(25)]
        text, markup = _render_favorites_page(favs, 2, 10, sort="date")
        assert "第 2/3 页" in text
        # Page 2 should show actress names 11-20
        assert "Actress 10" in text

    def test_page_clamped_to_max(self):
        favs = [self._make_fav(f"Actress {i}") for i in range(10)]
        text, _ = _render_favorites_page(favs, 999, 10, sort="date")
        assert "第 1/1 页" in text or "第" not in text  # no pages shown if single

    def test_no_actress_id(self):
        """Actress without ID still renders cleanly."""
        favs = [self._make_fav("No ID", ""), self._make_fav("Has ID", "ABC-001")]
        text, _ = _render_favorites_page(favs, 1, 10, sort="date")
        assert "No ID" in text
        assert "🆔 ABC-001" in text
        # No stray "🆔" after second actress
        assert text.count("🆔") == 1

    def test_last_query_info(self):
        favs = [self._make_fav("Queried"), self._make_fav("Never")]
        now = datetime.now().isoformat(timespec="seconds")
        lqm = {"Queried": now}
        text, _ = _render_favorites_page(favs, 1, 10, sort="date", last_query_map=lqm)
        assert "上次查询:" in text
        assert "刚刚" in text or "分钟前" in text
        assert "未查询" in text

    def test_sort_labels_in_display(self):
        favs = [self._make_fav("Test Actress")]
        text, _ = _render_favorites_page(favs, 1, 10, sort="name", last_query_map={})
        assert "名称" in text
        text2, _ = _render_favorites_page(favs, 1, 10, sort="recent", last_query_map={})
        assert "最近查询" in text2

    def test_keyboard_structure(self):
        favs = [self._make_fav(f"A{i}") for i in range(5)]
        _, markup = _render_favorites_page(favs, 1, 10, sort="date")
        keyboard = markup.inline_keyboard
        # Rows: button rows + nav + action
        assert len(keyboard) >= 2
        # All buttons are InlineKeyboardButton
        for row in keyboard:
            for btn in row:
                assert hasattr(btn, "text")
                assert hasattr(btn, "callback_data")
