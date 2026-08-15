"""admin_cmd: 权限判断与报告输出。"""
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from app.handlers.admin import admin_cmd


class TestAdminCmd:
    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        self._shared = shared_global
        # NOTE: conftest installs `admin_user_id` as a class-level PropertyMock on
        # the MagicMock class (return_value=None); setting an instance attribute is
        # a no-op (the data descriptor wins), so patch the class attribute instead.
        monkeypatch.setattr(
            type(shared_global.config), "admin_user_id", PropertyMock(return_value=12345)
        )
        monkeypatch.setattr(
            "app.handlers.admin.get_favorites_manager",
            AsyncMock(return_value=AsyncMock()),
        )

    @pytest.mark.asyncio
    async def test_no_permission(self, mock_update, mock_context):
        mock_update.effective_user.id = 99999
        mock_update.effective_message = AsyncMock()
        await admin_cmd(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_report(self, mock_update, mock_context):
        mock_update.effective_user.id = 12345
        mock_update.effective_message = AsyncMock()
        with patch("app.handlers.admin.collect_health", new=AsyncMock(return_value="report")):
            await admin_cmd(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_awaited_once_with(
            "report", parse_mode="HTML", disable_web_page_preview=True
        )
