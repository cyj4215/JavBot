"""健康检查基础设施：数据源状态注册表、错误日志环形缓冲、报告生成。"""

from __future__ import annotations

import html
import logging
import threading
import time
from collections import deque
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from .fav.manager import FavoritesManager
    from .handlers import _SharedState


class SourceStatus:
    """轻量数据源健康注册表（进程内）。"""

    _status: ClassVar[dict[str, tuple[float, str | None]]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def ok(cls, source: str) -> None:
        with cls._lock:
            cls._status[source] = (time.time(), None)

    @classmethod
    def fail(cls, source: str, error: str) -> None:
        with cls._lock:
            cls._status[source] = (time.time(), error[:200])

    @classmethod
    def snapshot(cls) -> list[dict]:
        with cls._lock:
            items = list(cls._status.items())
        return [{"source": name, "ts": ts, "error": err} for name, (ts, err) in items]


class ErrorRingHandler(logging.Handler):
    """保留最近 N 条 ERROR 日志的内存环形缓冲。"""

    def __init__(self, maxlen: int = 50) -> None:
        super().__init__(level=logging.ERROR)
        self._buf: deque[str] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        with self._lock:
            self._buf.append(f"{self.format(record)}")

    def recent(self, n: int = 5) -> list[str]:
        with self._lock:
            return list(self._buf)[-n:]


_error_handler = ErrorRingHandler()
_error_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
)


def install_error_handler() -> ErrorRingHandler:
    logging.getLogger().addHandler(_error_handler)
    return _error_handler


def _fmt_uptime(start_ts: float) -> str:
    secs = int(time.time() - start_ts)
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    return f"{days}天 {hours}小时 {minutes}分"


async def collect_health(shared: _SharedState, fav_mgr: FavoritesManager) -> str:
    """构建健康检查报告文本。"""
    from .main import START_TIME

    def _(key: str, *a: str) -> str:
        return shared.service.i18n.t(key, "zh_CN", *a)

    lines = [f"<b>🩺 {_('admin_title')}</b>", ""]
    lines.append(f"⏱ {_('admin_uptime')}：{_fmt_uptime(START_TIME)}")

    # 缓存
    lines.append("")
    lines.append(f"<b>📦 {_('admin_cache_hdr')}</b>")
    caches = {
        "profile": shared.service.profile_cache,
        "av_meta": shared.service.av_meta_cache,
        "wiki": shared.service.wiki_page_cache,
        "rank": shared.service.rank_cache,
        "javdb": shared.service._javdb_cache,
    }
    for name, cache in caches.items():
        s = cache.stats()
        lines.append(f"{name}: {s['size']} 条 / 命中率 {s['hit_rate'] * 100:.0f}%")

    # MySQL
    lines.append("")
    lines.append(f"<b>🗄 {_('admin_mysql_hdr')}</b>")
    try:
        pool = fav_mgr._pool
        probe = await fav_mgr._select_one("SELECT 1")
        mysql_ok = probe is not None
    except Exception:
        mysql_ok = False
    if mysql_ok:
        lines.append(f"{_('admin_pool')}: {pool.size}/{pool.maxsize} | SELECT 1: {_('admin_ok')}")
    else:
        lines.append(f"SELECT 1: {_('admin_fail')}")

    # 数据源
    lines.append("")
    lines.append(f"<b>🌐 {_('admin_sources_hdr')}</b>")
    snap = SourceStatus.snapshot()
    if not snap:
        lines.append(_("admin_no_data"))
    for src in snap:
        status = (
            _("admin_ok")
            if src["error"] is None
            else f"{_('admin_fail')} ({html.escape(src['error'])})"
        )
        lines.append(f"{src['source']}: {status}")

    # 回调存储
    lines.append("")
    lines.append(f"<b>🔐 {_('admin_callbacks_hdr')}</b>")
    try:
        from .secure_callback import get_callback_store

        st = get_callback_store().get_stats()
        lines.append(f"{_('admin_callbacks_valid')}: {st['valid_entries']}")
    except Exception:
        lines.append(_("admin_fail"))

    # 最近错误
    lines.append("")
    lines.append(f"<b>⚠️ {_('admin_logs_hdr')}</b>")
    recent = _error_handler.recent(5)
    if not recent:
        lines.append(_("admin_no_errors"))
    for entry in recent:
        lines.append(f"<code>{html.escape(entry[:300])}</code>")

    return "\n".join(lines)
