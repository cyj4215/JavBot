"""Global test configuration and shared fixtures."""
import os
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

# Prevent secure_callback from trying to write to /app/ in unit tests
os.environ.setdefault("CALLBACK_DB_PATH", "/tmp/test_javbot_callbacks.json")


@pytest.fixture
def mock_q():
    """Mock telegram.CallbackQuery with common async methods."""
    q = AsyncMock()
    q.data = ""
    q.message = AsyncMock()
    q.message.chat = AsyncMock()
    q.message.delete = AsyncMock()
    q.message.reply_text = AsyncMock(return_value=AsyncMock())
    q.message.reply_photo = AsyncMock(return_value=AsyncMock())
    q.message.reply_media_group = AsyncMock(return_value=[AsyncMock()])
    q.message.edit_message_text = AsyncMock()
    q.message.edit_message_media = AsyncMock()
    q.message.edit_message_caption = AsyncMock()
    q.message.edit_message_reply_markup = AsyncMock()
    q.message.photo = None
    q.answer = AsyncMock()
    return q


@pytest.fixture
def mock_update(mock_q):
    """Mock telegram.Update with effective_user + callback_query."""
    update = MagicMock()
    update.callback_query = mock_q
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    return update


@pytest.fixture
def mock_context():
    """Mock telegram.ext.ContextTypes.DEFAULT_TYPE."""
    return MagicMock()


@pytest.fixture
def mock_msg():
    """Mock telegram.Message for command handlers."""
    msg = AsyncMock()
    msg.chat = AsyncMock()
    msg.reply_text = AsyncMock(return_value=AsyncMock())
    msg.reply_photo = AsyncMock(return_value=AsyncMock())
    msg.reply_media_group = AsyncMock(return_value=[AsyncMock()])
    msg.delete = AsyncMock()
    return msg


@pytest.fixture
def mock_config():
    """Mock BotConfig with common defaults."""
    config = MagicMock()
    config.proxy_addr = ""
    config.send_latest_covers = True
    config.latest_cover_limit = 3
    config.latest_limit = 5
    config.top_limit = 5
    config.allowed_user_ids = set()
    config.magnet_limit = 5
    config.i18n_default_language = "zh_CN"
    config.uncensored = False
    config.rank_limit_default = 20
    config.rank_page_default = 1
    type(config).admin_user_id = PropertyMock(return_value=None)
    return config


@pytest.fixture
def mock_service():
    """Mock ActressService with async query_profile_async."""
    service = AsyncMock()
    service.query_profile_async = AsyncMock()
    service.get_av_magnets = MagicMock()
    service.i18n = MagicMock()
    service.i18n.t = MagicMock(side_effect=lambda key, lang=None, *a: key)
    service.i18n.DEFAULT_LANG = "zh_CN"
    return service


@pytest.fixture
def mock_shared(mock_config, mock_service):
    """Mock _SharedState with config + service."""
    shared = MagicMock()
    shared.config = mock_config
    shared.service = mock_service
    return shared


@pytest.fixture
def shared_global(mock_config, mock_service):
    """Install mock shared state into handlers.__init__ global (required by @require_auth)."""
    from app.handlers import _set_shared, _shared as orig_shared, _get_shared
    _set_shared(mock_config, mock_service)
    yield _get_shared()
    # Restore original value (might be None)
    import app.handlers as h
    h._shared = orig_shared
