"""run_magnet_reply: AV-ID searches get recorded to history."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers.magnet import run_magnet_reply
from app.models import JavBusWork


@pytest.fixture(autouse=True)
def _setup(shared_global, monkeypatch):
    import app.fav as fav_mod
    self_fav_mgr = AsyncMock()
    self_fav_mgr.increment_stat = AsyncMock()
    self_fav_mgr.record_favorite_query = AsyncMock(return_value=True)
    monkeypatch.setattr(
        fav_mod, "get_favorites_manager", AsyncMock(return_value=self_fav_mgr)
    )
    # run_magnet_reply calls these via asyncio.to_thread → keep them sync mocks
    # returning plain values (an AsyncMock would leak an un-awaited coroutine).
    svc = shared_global.service
    svc.get_av_meta = MagicMock(return_value=None)
    svc.get_av_magnets = MagicMock(return_value=[])
    shared_global.config.magnet_timeout = 5
    shared_global.config.magnet_limit = 5
    return self_fav_mgr


@pytest.mark.asyncio
async def test_records_query_with_user_id(mock_msg, _setup):
    await run_magnet_reply(mock_msg, "SSIS-123", user_id=12345)
    _setup.record_favorite_query.assert_awaited_once_with(12345, "SSIS-123")


@pytest.mark.asyncio
async def test_no_record_without_user_id(mock_msg, _setup):
    await run_magnet_reply(mock_msg, "SSIS-123")
    _setup.record_favorite_query.assert_not_called()


class TestDetailCardStars:
    """run_magnet_reply 详情卡包含主演与查看按钮 + 空结果 JavBus 引导。"""

    @pytest.fixture(autouse=True)
    def _setup(self, shared_global, monkeypatch):
        import app.fav as fav_mod

        self_fav_mgr = AsyncMock()
        self_fav_mgr.increment_stat = AsyncMock()
        self_fav_mgr.record_favorite_query = AsyncMock()
        monkeypatch.setattr(
            fav_mod, "get_favorites_manager", AsyncMock(return_value=self_fav_mgr)
        )
        # Same to_thread constraint as the module fixture: sync mocks only.
        svc = shared_global.service
        svc.get_av_meta = MagicMock(
            return_value=JavBusWork(
                id="SSIS-123",
                title="T",
                date="2026-08-01",
                img="",
                url="https://javbus.com/x",
                stars=["三上悠亜"],
            )
        )
        svc.get_av_magnets = MagicMock(return_value=[])
        shared_global.config.magnet_timeout = 5
        shared_global.config.magnet_limit = 5

    @pytest.mark.asyncio
    async def test_detail_card_has_star_and_button(self, mock_msg):
        from app.handlers.magnet import run_magnet_reply

        await run_magnet_reply(mock_msg, "SSIS-123")
        texts = [c.args[0] for c in mock_msg.reply_text.call_args_list]
        assert any("三上悠亜" in t for t in texts)
        detail_call = next(c for c in mock_msg.reply_text.call_args_list if "三上悠亜" in c.args[0])
        kb = detail_call.kwargs.get("reply_markup")
        assert kb is not None
        assert kb.inline_keyboard[0][0].callback_data.startswith("favquery:")

    @pytest.mark.asyncio
    async def test_empty_result_has_javbus_link_button(self, mock_msg):
        from app.handlers.magnet import run_magnet_reply
        from app.services.i18n import I18nService

        await run_magnet_reply(mock_msg, "SSIS-123")
        no_result = I18nService().t("magnet_no_result", "zh_CN")
        texts = [c.args[0] for c in mock_msg.reply_text.call_args_list]
        assert any(t == no_result for t in texts)
        call = next(c for c in mock_msg.reply_text.call_args_list if c.args[0] == no_result)
        kb = call.kwargs.get("reply_markup")
        assert kb is not None
        btn = kb.inline_keyboard[0][0]
        assert btn.url == "https://javbus.com/x"
