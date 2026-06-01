"""Unit tests for formatters — extended with profile keyboard callback tests."""
from datetime import datetime
from unittest.mock import patch

import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.formatters import format_profile, format_rankings, build_rank_keyboard, looks_like_av_id
from app.models import ActressProfile


class TestLooksLikeAvId:
    def test_standard_av_id(self):
        assert looks_like_av_id("SSIS-123")
        assert looks_like_av_id("MIDE-999")
        assert looks_like_av_id("ABP-001")

    def test_no_separator(self):
        assert looks_like_av_id("SSIS123")
        assert looks_like_av_id("ABP001")

    def test_lowercase(self):
        assert looks_like_av_id("ssis-123")

    def test_not_av_id(self):
        assert not looks_like_av_id("三上悠亜")
        assert not looks_like_av_id("hello world")
        assert not looks_like_av_id("12345")
        assert not looks_like_av_id("A-1")


class TestFormatRankings:
    def test_empty(self):
        result = format_rankings([], 1)
        assert "rank_empty" in result

    def test_with_stars(self):
        stars = [{"name": "Actress A"}, {"name": "Actress B"}, {"name": "Actress C"}]
        result = format_rankings(stars, 1)
        assert "Actress A" in result
        assert "Actress B" in result
        assert "Actress C" in result
        assert "rank_source" in result


class TestBuildRankKeyboard:
    def test_page_1(self):
        markup = build_rank_keyboard(20, 1)
        keyboard = markup.inline_keyboard
        assert len(keyboard) == 2
        assert "下一页" in keyboard[0][0].text
        assert "返回主菜单" in keyboard[1][0].text

    def test_page_5_max(self):
        markup = build_rank_keyboard(20, 5)
        keyboard = markup.inline_keyboard
        assert len(keyboard) == 2
        assert "上一页" in keyboard[0][0].text
        assert "返回主菜单" in keyboard[1][0].text

    def test_page_limits(self):
        markup = build_rank_keyboard(0, 100)
        keyboard = markup.inline_keyboard
        assert len(keyboard) > 0


def _make_profile(
    found=True,
    star_name="三上悠亜",
    star_id="SSIS-123",
    extra_info=None,
    avatar_url="https://javdb.com/avatar.jpg",
):
    return ActressProfile(
        found=found,
        query=star_name,
        star_name=star_name,
        star_id=star_id,
        extra_info=extra_info or {},
        avatar_url=avatar_url,
    )


class TestFormatProfileKeyboard:
    """Verify the profile keyboard structure and callback data after today's changes."""

    def test_latest_works_button_uses_works_callback(self):
        """profile_latest_works must use 'works' prefix, not 'favquery'."""
        profile = _make_profile()
        text, markup = format_profile(profile, user_id=12345, _t=lambda k, *a: k)
        assert markup is not None

        for row in markup.inline_keyboard:
            for btn in row:
                if "works" in btn.text.lower() or "latest" in btn.text.lower() or "最新" in btn.text:
                    assert isinstance(btn.callback_data, str)
                    assert btn.callback_data.startswith("works:"), (
                        f"Expected 'works:' prefix, got: {btn.callback_data[:30]}"
                    )

    def test_no_profile_view_works_separate_button(self):
        """profile_view_works button should be removed; only one works entry."""
        profile = _make_profile()
        text, markup = format_profile(profile, user_id=12345, _t=lambda k, *a: k)
        assert markup is not None

        works_button_count = sum(
            1 for row in markup.inline_keyboard
            for btn in row
            if isinstance(btn.callback_data, str) and btn.callback_data.startswith("works:")
        )
        assert works_button_count == 1, (
            f"Expected exactly 1 'works:' button, found {works_button_count}"
        )

    def test_favorite_button_uses_favnow_callback(self):
        profile = _make_profile()
        text, markup = format_profile(profile, user_id=12345, is_favorite=False, _t=lambda k, *a: k)
        assert markup is not None

        fav_btn = None
        for row in markup.inline_keyboard:
            for btn in row:
                if hasattr(btn, 'callback_data') and isinstance(btn.callback_data, str) and btn.callback_data.startswith("favnow:"):
                    fav_btn = btn
        assert fav_btn is not None, "Expected 'favnow:' button in non-favorite keyboard"

    def test_unfavorite_button_uses_unfavnow_callback(self):
        profile = _make_profile()
        text, markup = format_profile(profile, user_id=12345, is_favorite=True, _t=lambda k, *a: k)
        assert markup is not None

        unfav_btn = None
        for row in markup.inline_keyboard:
            for btn in row:
                if hasattr(btn, 'callback_data') and isinstance(btn.callback_data, str) and btn.callback_data.startswith("unfavnow:"):
                    unfav_btn = btn
        assert unfav_btn is not None, "Expected 'unfavnow:' button in favorite keyboard"

    def test_no_magnet_button_on_profile(self):
        """Profile keyboard should NOT have a magnet button — magnet queries need AV ID, not actress name."""
        profile = _make_profile()
        text, markup = format_profile(profile, user_id=12345, _t=lambda k, *a: k)
        assert markup is not None

        magnet_btn = None
        for row in markup.inline_keyboard:
            for btn in row:
                if hasattr(btn, 'callback_data') and isinstance(btn.callback_data, str) and btn.callback_data.startswith("magnet:"):
                    magnet_btn = btn
        assert magnet_btn is None, "Profile should not have a magnet button (no AV ID context)"

    def test_back_data_button(self):
        profile = _make_profile()
        text, markup = format_profile(profile, user_id=12345, _t=lambda k, *a: k, back_data="myfav:page:1:date")
        assert markup is not None

        back_btn = None
        for row in markup.inline_keyboard:
            for btn in row:
                if btn.callback_data == "myfav:page:1:date":
                    back_btn = btn
        assert back_btn is not None

    def test_menu_return_button(self):
        profile = _make_profile()
        text, markup = format_profile(profile, user_id=12345, _t=lambda k, *a: k)
        assert markup is not None

        menu_btn = None
        for row in markup.inline_keyboard:
            for btn in row:
                if btn.callback_data == "menu:search":
                    menu_btn = btn
        assert menu_btn is not None

    def test_keyboard_structure_not_found(self):
        profile = _make_profile(found=False)
        text, markup = format_profile(profile, user_id=12345, _t=lambda k, *a: k)
        assert markup is not None
        # Not-found profile should not have fav/works buttons
        for row in markup.inline_keyboard:
            for btn in row:
                assert not btn.callback_data.startswith("works:")
                assert not btn.callback_data.startswith("favnow:")
