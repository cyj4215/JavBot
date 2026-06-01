"""Tests for favorite_query_callback: favquery, favnow, unfavnow, myfav page/sort."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers.favorites import _parse_actress_names, _fuzzy_match


class TestParseActressNames:
    def test_single_name(self):
        assert _parse_actress_names("三上悠亜") == ["三上悠亜"]

    def test_comma_separated(self):
        assert _parse_actress_names("三上悠亜, 河北彩花") == ["三上悠亜", "河北彩花"]

    def test_semicolon_separated(self):
        assert _parse_actress_names("三上悠亜; 河北彩花") == ["三上悠亜", "河北彩花"]

    def test_chinese_comma(self):
        assert _parse_actress_names("三上悠亜，河北彩花") == ["三上悠亜", "河北彩花"]

    def test_mixed_separators(self):
        assert _parse_actress_names("A,B；C") == ["A", "B", "C"]

    def test_whitespace_trimmed(self):
        assert _parse_actress_names("  A  ,  B  ") == ["A", "B"]

    def test_empty_input(self):
        assert _parse_actress_names("") == []

    def test_only_separators(self):
        assert _parse_actress_names(",,,,") == []


class TestFuzzyMatch:
    def test_exact_match(self):
        assert _fuzzy_match("三上悠亜", "三上悠亜")

    def test_substring_match(self):
        assert _fuzzy_match("三上", "三上悠亜")
        assert _fuzzy_match("三上悠亜", "三上")

    def test_case_insensitive(self):
        assert _fuzzy_match("YUA", "yua")
        assert _fuzzy_match("yua", "YUA")

    def test_no_match(self):
        assert not _fuzzy_match("abc", "def")

    def test_whitespace_handling(self):
        assert _fuzzy_match(" 三上 ", "三上悠亜")


_HANDLER_MAP: dict = {}


class TestCallbackFavquery:
    """callback_favquery: query actress profile from favorites."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        from app.handlers.favorites import callback_favquery
        self._handler = callback_favquery
        self._svc = shared_global.service
        self._svc.query_profile_async.return_value = _fake_profile(found=True, star_name="TestActress")
        import app.handlers.favorites as hf_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.record_favorite_query = AsyncMock()
        monkeypatch.setattr(hf_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))

    async def _call(self, update, context):
        await self._handler(update, context)

    async def test_queries_profile(self, mock_update, mock_context, mock_q):
        mock_q.data = _signed_favquery("TestActress")
        await self._call(mock_update, mock_context)
        self._svc.query_profile_async.assert_awaited_with("TestActress")

    async def test_expired_shows_alert(self, mock_update, mock_context, mock_q):
        mock_q.data = "favquery:bad"
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once()

    async def test_records_query(self, mock_update, mock_context, mock_q):
        mock_q.data = _signed_favquery("TestActress")
        await self._call(mock_update, mock_context)
        self._fav_mgr.record_favorite_query.assert_awaited()

    async def test_service_exception_handled(self, mock_update, mock_context, mock_q):
        self._svc.query_profile_async.side_effect = Exception("network error")
        mock_q.data = _signed_favquery("TestActress")
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited()


class TestCallbackFavnow:
    """callback_favnow: add actress to favorites."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        from app.handlers.favorites import callback_favnow
        self._handler = callback_favnow
        self._svc = shared_global.service
        self._svc.query_profile_async.return_value = _fake_profile(found=True, star_name="TestActress")
        import app.handlers.favorites as hf_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.add_favorite.return_value = True
        monkeypatch.setattr(hf_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))

    async def _call(self, update, context):
        await self._handler(update, context)

    async def test_adds_favorite(self, mock_update, mock_context, mock_q):
        mock_q.data = _signed_favnow("TestActress")
        await self._call(mock_update, mock_context)
        self._fav_mgr.add_favorite.assert_awaited()

    async def test_expired_shows_alert(self, mock_update, mock_context, mock_q):
        mock_q.data = "favnow:bad"
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once()


class TestCallbackUnfavnow:
    """callback_unfavnow: remove actress from favorites."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        from app.handlers.favorites import callback_unfavnow
        self._handler = callback_unfavnow
        import app.handlers.favorites as hf_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.remove_favorite.return_value = True
        monkeypatch.setattr(hf_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))

    async def _call(self, update, context):
        await self._handler(update, context)

    async def test_removes_favorite(self, mock_update, mock_context, mock_q):
        mock_q.data = _signed_unfavnow("TestActress")
        await self._call(mock_update, mock_context)
        self._fav_mgr.remove_favorite.assert_awaited()

    async def test_expired_shows_alert(self, mock_update, mock_context, mock_q):
        mock_q.data = "unfavnow:bad"
        await self._call(mock_update, mock_context)
        mock_q.answer.assert_awaited_once()


class TestCallbackMyfavPage:
    """callback_myfav_page: paginate favorites list."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        from app.handlers.favorites import callback_myfav_page
        self._handler = callback_myfav_page
        import app.handlers.favorites as hf_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_favorites.return_value = {"items": [
            {"actress_name": "A", "actress_id": "A-001", "created_at": "2026-05-01"},
        ]}
        monkeypatch.setattr(hf_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))

    async def _call(self, update, context):
        await self._handler(update, context)

    async def test_page_with_favorites(self, mock_update, mock_context, mock_q):
        mock_q.data = "myfav:page:1:date"
        await self._call(mock_update, mock_context)
        mock_q.edit_message_text.assert_awaited_once()

    async def test_empty_shows_message(self, mock_update, mock_context, mock_q):
        self._fav_mgr.get_favorites.return_value = {"items": []}
        mock_q.data = "myfav:page:1:date"
        await self._call(mock_update, mock_context)
        mock_q.edit_message_text.assert_awaited_once()


class TestCallbackMyfavSort:
    """callback_myfav_sort: cycle sort order."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        from app.handlers.favorites import callback_myfav_sort
        self._handler = callback_myfav_sort
        import app.handlers.favorites as hf_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_favorites.return_value = {"items": [
            {"actress_name": "A", "actress_id": "A-001", "created_at": "2026-05-01"},
        ]}
        monkeypatch.setattr(hf_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))

    async def test_sort_cycles(self, mock_update, mock_context, mock_q):
        mock_q.data = "myfav:sort:date:1"
        await self._handler(mock_update, mock_context)
        mock_q.edit_message_text.assert_awaited_once()


# ── Helpers ──

def _fake_profile(found=True, star_name="Test", query="Test", latest_works=None):
    from app.models import ActressProfile
    return ActressProfile(
        found=found, query=query, star_name=star_name,
        star_id=star_name.upper() if found else "",
        latest_works=latest_works or [],
        extra_info={},
        avatar_url="",
    )


def _signed_favquery(name: str) -> str:
    from app.secure_callback import short_callback
    return short_callback("favquery", name)


def _signed_favnow(name: str) -> str:
    from app.secure_callback import short_callback
    return short_callback("favnow", name)


def _signed_unfavnow(name: str) -> str:
    from app.secure_callback import short_callback
    return short_callback("unfavnow", name)
