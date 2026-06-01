"""Unit tests for favorites UI helpers (_time_ago, _sort_favorites, _render_favorites_page).

Pure functions — no DB or Telegram API required.
"""
from datetime import datetime, timedelta

import pytest
from telegram import InlineKeyboardMarkup

from app.formatters import time_ago, sort_favorites, render_favorites_page


def _iso_now():
    return datetime.now().isoformat(timespec="seconds")


def _iso_minutes_ago(n):
    return (datetime.now() - timedelta(minutes=n)).isoformat(timespec="seconds")


def _iso_days_ago(n):
    return (datetime.now() - timedelta(days=n)).isoformat(timespec="seconds")


class TestTimeAgo:
    def test_empty(self):
        assert time_ago("") == ""

    def test_just_now(self):
        ts = _iso_now()
        assert time_ago(ts) == "刚刚"

    def test_minutes_ago(self):
        ts = _iso_minutes_ago(5)
        assert time_ago(ts) == "5分钟前"

    def test_hours_ago(self):
        ts = _iso_minutes_ago(180)
        assert time_ago(ts) == "3小时前"

    def test_days_ago(self):
        ts = _iso_days_ago(3)
        assert time_ago(ts) == "3天前"

    def test_months_ago(self):
        ts = _iso_days_ago(45)
        assert time_ago(ts) == "1月前"

    def test_invalid_format(self):
        assert time_ago("not-a-date") == "not-a-date"


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
        result = sort_favorites(favs, "name", query_map)
        names = [f["actress_name"] for f in result]
        assert names == ["A Actress", "B Actress", "C Actress"]

    def test_sort_by_date(self, favs, query_map):
        result = sort_favorites(favs, "date", query_map)
        names = [f["actress_name"] for f in result]
        assert names == ["B Actress", "C Actress", "A Actress"]

    def test_sort_by_recent(self, favs, query_map):
        result = sort_favorites(favs, "recent", query_map)
        names = [f["actress_name"] for f in result]
        assert names == ["B Actress", "A Actress", "C Actress"]

    def test_sort_invalid_fallback_to_date(self, favs, query_map):
        result = sort_favorites(favs, "invalid", query_map)
        names = [f["actress_name"] for f in result]
        assert names == ["B Actress", "C Actress", "A Actress"]


class TestRenderFavoritesPage:
    def _make_fav(self, name, actress_id="", created_at="2026-05-01 10:00:00"):
        return {"actress_name": name, "actress_id": actress_id, "created_at": created_at}

    def test_empty_favorites(self):
        text, markup = render_favorites_page([], 1, 6, sort="date")
        assert "📚" in text
        assert "0 位" in text
        assert markup is not None

    def test_single_page(self):
        favs = [self._make_fav("三上悠亜", "SSIS-123"), self._make_fav("河北彩花", "SSIS-999")]
        text, markup = render_favorites_page(favs, 1, 6, sort="date")
        assert "三上悠亜" in text
        assert "河北彩花" in text
        assert "🆔" not in text  # no extra info per line
        assert "2 位" in text
        keyboard = markup.inline_keyboard
        assert len(keyboard) >= 2

    def test_pagination(self):
        favs = [self._make_fav(f"Actress {i}") for i in range(25)]
        text, markup = render_favorites_page(favs, 1, 6, sort="date")
        assert "第 1/5 页" in text
        assert "25 位" in text
        keyboard = markup.inline_keyboard
        assert len(keyboard) >= 2

    def test_page_2(self):
        favs = [self._make_fav(f"Actress {i}") for i in range(25)]
        text, _ = render_favorites_page(favs, 2, 6, sort="date")
        assert "第 2/5 页" in text
        assert "Actress 6" in text

    def test_page_clamped(self):
        favs = [self._make_fav(f"A{i}") for i in range(5)]
        text, _ = render_favorites_page(favs, 999, 6, sort="date")
        assert "第 1/1 页" in text or "第" not in text

    def test_no_latest_works_button(self):
        favs = [self._make_fav("Test")]
        _, markup = render_favorites_page(favs, 1, 6, sort="date")
        for row in markup.inline_keyboard:
            for btn in row:
                assert "最新作品" not in btn.text

    def test_keyboard_3_per_row(self):
        favs = [self._make_fav(f"A{i}") for i in range(6)]
        _, markup = render_favorites_page(favs, 1, 6, sort="date")
        keyboard = markup.inline_keyboard
        # 2 rows of 3 + nav row
        assert len(keyboard) == 3

    def test_sort_labels_in_display(self):
        favs = [self._make_fav("Test")]
        text, _ = render_favorites_page(favs, 1, 6, sort="name")
        assert "名称" in text
        text2, _ = render_favorites_page(favs, 1, 6, sort="recent")
        assert "最近查询" in text2

    def test_keyboard_structure(self):
        favs = [self._make_fav(f"A{i}") for i in range(5)]
        _, markup = render_favorites_page(favs, 1, 6, sort="date")
        keyboard = markup.inline_keyboard
        assert len(keyboard) >= 2
        for row in keyboard:
            for btn in row:
                assert hasattr(btn, "text")
                assert hasattr(btn, "callback_data")
