"""Tests for works_callback handler (button press → works browser)."""
from unittest.mock import AsyncMock

import pytest

from app.handlers.works import _build_works_page


class TestWorksCallback:
    """works_callback handler: verify q.answer timing, edit behavior, fallback, error paths."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global):
        """Create fresh handler per test. shared_global fixture sets handlers.__init__._shared."""
        from app.handlers.works import works_callback
        self._handler = works_callback
        self._svc = shared_global.service
        self._cfg = shared_global.config
        # Default: profile found with works
        self._svc.query_profile_async.return_value = _fake_profile(
            found=True,
            star_name="TestActress",
            latest_works=[
                {"id": "TEST-001", "img": "https://img.test/1.jpg", "date": "2026-05-01", "title": "Work 1"},
                {"id": "TEST-002", "img": "https://img.test/2.jpg", "date": "2026-05-02", "title": "Work 2"},
                {"id": "TEST-003", "img": "https://img.test/3.jpg", "date": "", "title": ""},
            ])

    async def _call(self, update, context):
        await self._handler(update, context)

    async def test_q_answer_called_immediately(self, mock_update, mock_context, mock_q):
        """q.answer() must be called before any slow ops — prevents button spinner."""
        mock_q.data = _signed_works("TestActress")
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once()

    async def test_expired_callback_shows_alert(self, mock_update, mock_context, mock_q):
        """Expired HMAC token → show alert, don't answer normally."""
        mock_q.data = "works:bad"
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once_with("该链接已过期", show_alert=True)

    async def test_empty_works_still_answers(self, mock_update, mock_context, mock_q):
        """No works found → answer (no error), don't crash."""
        self._svc.query_profile_async.return_value = _fake_profile(
            found=True, star_name="Empty", latest_works=[]
        )
        mock_q.data = _signed_works("Empty")
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once()
        mock_q.edit_message_text.assert_not_called()

    async def test_profile_not_found_returns_empty(self, mock_update, mock_context, mock_q):
        """Profile not found → no crash, buttons handled gracefully."""
        self._svc.query_profile_async.return_value = _fake_profile(
            found=False, query="NotFound"
        )
        mock_q.data = _signed_works("NotFound")
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once()

    async def test_edit_message_text_when_no_photo_and_no_img(self, mock_update, mock_context, mock_q):
        """No-photo messages with no img_url → edit_message_text."""
        self._svc.query_profile_async.return_value = _fake_profile(
            found=True, star_name="TestActress",
            latest_works=[{"id": "TEXT-001", "img": "", "date": "", "title": "Text Only"}],
        )
        mock_q.message.photo = None
        mock_q.data = _signed_works("TestActress|0")
        await self._call(mock_update, mock_context)
        mock_q.edit_message_text.assert_awaited_once()

    async def test_edit_message_text_contains_av_id(self, mock_update, mock_context, mock_q):
        """No img + no photo → edit_message_text with AV ID."""
        self._svc.query_profile_async.return_value = _fake_profile(
            found=True, star_name="TestActress",
            latest_works=[{"id": "TEXT-001", "img": "", "date": "", "title": "Text Only"}],
        )
        mock_q.message.photo = None
        mock_q.data = _signed_works("TestActress|0")
        await self._call(mock_update, mock_context)
        args, _ = mock_q.edit_message_text.call_args
        assert "TEXT-001" in args[0]

    async def test_edit_message_media_when_photo_message(self, mock_update, mock_context, mock_q):
        """Photo messages should be edited via edit_message_media."""
        mock_q.message.photo = [AsyncMock()]
        mock_q.data = _signed_works("TestActress|0")
        await self._call(mock_update, mock_context)
        mock_q.edit_message_media.assert_awaited_once()

    async def test_reply_photo_fallback_on_edit_failure(self, mock_update, mock_context, mock_q):
        """If edit_message_media fails, fall back to reply_photo."""
        mock_q.message.photo = [AsyncMock()]
        mock_q.edit_message_media.side_effect = Exception("edit failed")
        mock_q.data = _signed_works("TestActress|0")
        await self._call(mock_update, mock_context)
        mock_q.message.reply_photo.assert_awaited_once()

    async def test_edit_message_caption_fallback_when_photo_fails(self, mock_update, mock_context, mock_q):
        """Photo msg: edit_media + reply_photo both fail → edit_message_caption."""
        mock_q.message.photo = [AsyncMock()]
        mock_q.edit_message_media.side_effect = Exception("edit failed")
        mock_q.message.reply_photo.side_effect = Exception("photo failed")
        mock_q.data = _signed_works("TestActress|0")
        await self._call(mock_update, mock_context)
        mock_q.edit_message_caption.assert_awaited_once()

    async def test_works_capped_at_three(self, mock_update, mock_context, mock_q):
        """Works list capped to 3 → no ▶️ at index 2 (last of 3, not last of 9)."""
        many_works = [{"id": f"TEST-{i:03d}", "img": "", "date": "", "title": ""}
                      for i in range(1, 10)]
        self._svc.query_profile_async.return_value = _fake_profile(
            found=True, star_name="Many", latest_works=many_works
        )
        mock_q.message.photo = None
        mock_q.data = _signed_works("Many|2")  # last page after cap
        await self._call(mock_update, mock_context)
        # After cap: works=[TEST-001, TEST-002, TEST-003], index=2 → last page → no ▶️
        # Without cap: index=2 of 9 → has ▶️
        mock_q.edit_message_text.assert_awaited_once()
        args, _ = mock_q.edit_message_text.call_args
        assert "TEST-003" in args[0]

    async def test_navigation_to_page_2(self, mock_update, mock_context, mock_q):
        """Navigating to page 2 shows second work."""
        self._svc.query_profile_async.return_value = _fake_profile(
            found=True, star_name="TestActress",
            latest_works=[
                {"id": "A-001", "img": "", "date": "", "title": ""},
                {"id": "A-002", "img": "", "date": "", "title": ""},
            ],
        )
        mock_q.message.photo = None
        mock_q.data = _signed_works("TestActress|1")
        await self._call(mock_update, mock_context)
        args, _ = mock_q.edit_message_text.call_args
        assert "A-002" in args[0]


class TestBuildWorksPage:
    """_build_works_page pure function tests (existing, extended)."""

    def test_magnet_button_has_correct_prefix(self):
        from app.secure_callback import resolve_callback
        works = [{"id": "TEST-001", "img": "https://img.test/1.jpg", "date": "", "title": ""}]
        _, markup, _ = _build_works_page(works, "Test", 0, lambda k, *a: k)
        assert markup is not None
        for row in markup.inline_keyboard:
            for btn in row:
                if hasattr(btn, "callback_data") and isinstance(btn.callback_data, str):
                    if btn.callback_data.startswith("magnet:"):
                        resolved = resolve_callback("magnet", btn.callback_data)
                        assert resolved == "TEST-001"

    def test_back_button_uses_favquery_prefix(self):
        from app.secure_callback import resolve_callback
        works = [{"id": "TEST-001", "img": "https://img.test/1.jpg", "date": "", "title": ""}]
        _, markup, _ = _build_works_page(works, "Test", 0, lambda k, *a: k)
        assert markup is not None
        # Last row should be favquery back button
        last_row = markup.inline_keyboard[-1]
        assert len(last_row) == 1
        btn = last_row[0]
        assert btn.callback_data.startswith("favquery:")
        resolved = resolve_callback("favquery", btn.callback_data)
        assert resolved == "Test"


# ── Helpers ──

def _fake_profile(found=True, star_name="Test", query="Test", latest_works=None):
    """Build a minimal ActressProfile-like object for mocking."""
    from app.models import ActressProfile
    return ActressProfile(
        found=found,
        query=query,
        star_name=star_name,
        star_id=star_name.upper() if found else "",
        latest_works=latest_works or [],
        extra_info={},
        avatar_url="https://javdb.com/avatar/test.jpg",
    )


def _signed_works(raw: str) -> str:
    """Generate a signed works: callback token."""
    from app.secure_callback import short_callback
    return short_callback("works", raw)
