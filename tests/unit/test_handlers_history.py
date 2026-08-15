"""Tests for history handler: history_cmd, history_page_callback, _render_history_page."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import InlineKeyboardMarkup

from app.handlers.history import _render_history_page


class TestRenderHistoryPage:
    """_render_history_page: pagination, keyboard structure."""

    def _make_queries(self, count=5):
        return [
            {"actress_name": f"Actress {i}", "query_time": f"2026-07-0{i+1} 10:00:00"}
            for i in range(count)
        ]

    def test_empty_queries(self):
        text, markup = _render_history_page([], 1, 0)
        assert "📜" in text
        assert "0" in text
        assert markup is not None

    def test_single_page(self):
        queries = self._make_queries(5)
        text, markup = _render_history_page(queries, 1, 5)
        assert "Actress 0" in text
        assert "Actress 4" in text
        assert "5 条" in text
        assert markup is not None

    def test_pagination_buttons_appear(self):
        queries = self._make_queries(15)
        text, markup = _render_history_page(queries, 1, 15)
        assert "第 1/2" in text
        keyboard = markup.inline_keyboard
        has_next = any("▶️" in btn.text for row in keyboard for btn in row)
        assert has_next

    def test_page_2(self):
        queries = self._make_queries(15)
        text, _ = _render_history_page(queries, 2, 15)
        assert "第 2/2" in text

    def test_prev_button_on_page_2(self):
        queries = self._make_queries(15)
        text, markup = _render_history_page(queries, 2, 15)
        keyboard = markup.inline_keyboard
        has_prev = any("◀️" in btn.text for row in keyboard for btn in row)
        assert has_prev

    def test_no_nav_on_single_page(self):
        queries = self._make_queries(5)
        text, markup = _render_history_page(queries, 1, 5)
        keyboard = markup.inline_keyboard
        for row in keyboard:
            for btn in row:
                assert "◀️" not in btn.text
                assert "▶️" not in btn.text

    def test_re_search_buttons(self):
        queries = self._make_queries(3)
        text, markup = _render_history_page(queries, 1, 3)
        keyboard = markup.inline_keyboard
        # Each query should have a search button
        assert len(keyboard) >= 3

    def test_menu_return_button(self):
        queries = [{"actress_name": "A", "query_time": "2026-07-01 10:00:00"}]
        text, markup = _render_history_page(queries, 1, 1)
        assert any(
            "menu:search" in btn.callback_data
            for row in markup.inline_keyboard for btn in row
        )

    def test_av_id_routed_to_magnet_button(self):
        queries = [
            {"actress_name": "SSIS-123", "query_time": "2026-07-01 10:00:00"},
            {"actress_name": "三上悠亜", "query_time": "2026-07-01 10:00:00"},
        ]
        _, markup = _render_history_page(queries, 1, 2)
        keyboard = markup.inline_keyboard
        magnet_btn = keyboard[0][0]
        search_btn = keyboard[1][0]
        assert magnet_btn.callback_data.startswith("magnet:")
        assert search_btn.callback_data.startswith("search:")


class TestHistoryCmd:
    """history_cmd: display, empty state."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        from app.handlers.history import history_cmd
        self._handler = history_cmd
        import app.handlers.history as hist_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_recent_favorite_queries.return_value = [
            {"actress_name": "A", "query_time": "2026-07-01 10:00:00"},
        ]
        monkeypatch.setattr(hist_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))

    async def _call(self, update, context):
        """Call decorated handler (Telegram-style: update, context only)."""
        await self._handler(update, context)

    async def test_empty_history(self, mock_update, mock_context):
        """No history → show empty message."""
        self._fav_mgr.get_recent_favorite_queries.return_value = []
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once()

    async def test_shows_history(self, mock_update, mock_context):
        """Has history → show formatted page."""
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once()

    async def test_page_arg(self, mock_update, mock_context):
        """Page argument → pass to render."""
        mock_context.args = ["2"]
        mock_update.effective_message = AsyncMock()
        await self._call(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once()


class TestHistoryPageCallback:
    """history_page_callback: pagination navigation."""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        import app.handlers.history as hist_mod
        self._fav_mgr = AsyncMock()
        self._fav_mgr.get_recent_favorite_queries.return_value = [
            {"actress_name": f"A{i}", "query_time": "2026-07-01 10:00:00"}
            for i in range(15)
        ]
        monkeypatch.setattr(hist_mod, "get_favorites_manager", AsyncMock(return_value=self._fav_mgr))

    @pytest.mark.asyncio
    async def test_page_navigation(self, mock_update, mock_context, mock_q):
        """Page navigation → edit message."""
        from app.handlers.history import history_page_callback
        mock_q.data = "hist:page:2"
        mock_update.callback_query = mock_q
        # Ensure shared state is available
        from app.handlers import _get_shared
        shared = _get_shared()
        shared.config.allowed_user_ids = {12345}
        await history_page_callback(mock_update, mock_context)
        mock_q.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_history(self, mock_update, mock_context, mock_q):
        """No history → edit message."""
        from app.handlers.history import history_page_callback
        self._fav_mgr.get_recent_favorite_queries.return_value = []
        mock_q.data = "hist:page:1"
        mock_update.callback_query = mock_q
        from app.handlers import _get_shared
        shared = _get_shared()
        shared.config.allowed_user_ids = {12345}
        await history_page_callback(mock_update, mock_context)
        mock_q.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auth_required(self, mock_update, mock_context, mock_q):
        """Unauthorized user → show alert."""
        from app.handlers.history import history_page_callback
        mock_q.data = "hist:page:1"
        mock_update.callback_query = mock_q
        from app.handlers import _get_shared
        shared = _get_shared()
        shared.config.allowed_user_ids = {99999}
        mock_update.effective_user.id = 12345
        await history_page_callback(mock_update, mock_context)
        mock_q.answer.assert_awaited_once_with("无权限使用", show_alert=True)