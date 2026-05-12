from app.formatters import format_rankings, build_rank_keyboard, looks_like_av_id


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
