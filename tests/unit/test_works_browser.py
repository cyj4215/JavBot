"""Tests for works browser: _build_works_page, works list capping."""
from telegram import InlineKeyboardMarkup

from app.handlers.works import _build_works_page


def _make_work(av_id, date="2026-05-01", title="Test Title", img="https://javbus.com/cover/xxx.jpg"):
    return {"id": av_id, "date": date, "title": title, "img": img}


def _t(key, *args):
    """Minimal i18n stub: returns key or formats with args."""
    if args:
        return f"{key}:{':'.join(str(a) for a in args)}"
    return key


class TestBuildWorksPage:
    def test_empty_works(self):
        caption, keyboard, img_url = _build_works_page([], "Test", 0, _t)
        assert "works_empty" in caption
        assert keyboard is None
        assert img_url is None

    def test_single_work(self):
        works = [_make_work("SSIS-123")]
        caption, keyboard, img_url = _build_works_page(works, "三上悠亜", 0, _t)
        assert "SSIS-123" in caption
        assert "works_page:1:1" in caption  # page 1 of 1
        assert img_url == "https://javbus.com/cover/xxx.jpg"
        assert keyboard is not None

    def test_multiple_works_page_0(self):
        works = [_make_work("A-001"), _make_work("A-002"), _make_work("A-003")]
        caption, keyboard, img_url = _build_works_page(works, "Test", 0, _t)
        assert "A-001" in caption
        assert "works_page:1:3" in caption

    def test_multiple_works_page_1(self):
        works = [_make_work("A-001"), _make_work("A-002"), _make_work("A-003")]
        caption, keyboard, img_url = _build_works_page(works, "Test", 1, _t)
        assert "A-002" in caption
        assert "works_page:2:3" in caption

    def test_index_clamped_negative(self):
        works = [_make_work("A-001")]
        caption, _, _ = _build_works_page(works, "Test", -5, _t)
        assert "A-001" in caption

    def test_index_clamped_overflow(self):
        works = [_make_work("A-001")]
        caption, _, _ = _build_works_page(works, "Test", 99, _t)
        assert "A-001" in caption

    def test_navigation_buttons_page_0_of_3(self):
        works = [_make_work("A-001"), _make_work("A-002"), _make_work("A-003")]
        caption, keyboard, img_url = _build_works_page(works, "Test", 0, _t)
        assert keyboard is not None
        rows = keyboard.inline_keyboard
        nav_row = rows[0]
        texts = [btn.text for btn in nav_row]
        # Page 0: ▶️ (next) and magnet, no ◀️
        assert "◀️" not in texts[0]
        assert "▶️" in texts if len(nav_row) > 1 else True

    def test_navigation_buttons_page_2_of_3(self):
        works = [_make_work("A-001"), _make_work("A-002"), _make_work("A-003")]
        caption, keyboard, img_url = _build_works_page(works, "Test", 2, _t)
        assert keyboard is not None
        rows = keyboard.inline_keyboard
        nav_row = rows[0]
        texts = [btn.text for btn in nav_row]
        # Page 2 (last): ◀️ (prev) and magnet, no ▶️
        assert "▶️" not in texts

    def test_back_to_profile_button_exists(self):
        works = [_make_work("A-001")]
        caption, keyboard, img_url = _build_works_page(works, "Test", 0, _t)
        assert keyboard is not None
        rows = keyboard.inline_keyboard
        # Last row should be the back-to-profile button
        last_row = rows[-1]
        assert len(last_row) == 1
        assert last_row[0].callback_data.startswith("favquery:")

    def test_works_list_capped_at_three(self):
        """Simulate the 3-page cap from works_callback: works[:3]."""
        works = [
            _make_work(f"A-{i:03d}", date=f"2026-05-{i:02d}")
            for i in range(1, 10)
        ]
        capped = works[:3]
        assert len(capped) == 3
        caption, keyboard, _ = _build_works_page(capped, "Test", 0, _t)
        assert "works_page:1:3" in caption

    def test_capped_works_navigation_ends_at_3(self):
        """Verify navigation of 3 capped works works correctly."""
        works = [_make_work(f"A-{i:03d}") for i in range(1, 4)]
        # Page 2 (last, index 2)
        caption, keyboard, _ = _build_works_page(works, "Test", 2, _t)
        assert "A-003" in caption
        # No next button
        for row in keyboard.inline_keyboard:
            for btn in row:
                assert "▶️" not in btn.text

    def test_work_without_img(self):
        works = [{"id": "NO-IMG", "date": "", "title": "", "img": ""}]
        caption, keyboard, img_url = _build_works_page(works, "Test", 0, _t)
        assert "NO-IMG" in caption
        assert img_url == ""

    def test_work_without_id(self):
        works = [{"id": "", "date": "", "title": "", "img": "https://example.com/img.jpg"}]
        caption, keyboard, img_url = _build_works_page(works, "Test", 0, _t)
        assert img_url == "https://example.com/img.jpg"
        # No magnet button for work without id
        if keyboard:
            for row in keyboard.inline_keyboard:
                for btn in row:
                    if hasattr(btn, 'callback_data') and isinstance(btn.callback_data, str):
                        assert not btn.callback_data.startswith("magnet:")
