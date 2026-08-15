"""JavBusService: AV meta 提取主演字段。"""
from unittest.mock import MagicMock

from app.services.javbus_service import JavBusService


def _make_service(av_dict):
    javbus = MagicMock()
    javbus.get_av_by_id.return_value = (200, av_dict)
    javbus.get_av_magnets.return_value = (200, [])
    cache = MagicMock()
    cache.get.return_value = None
    return JavBusService(
        javbus_util=javbus,
        av_meta_cache=cache,
        javbus_limiter=MagicMock(),
        uncensored=False,
    )


def test_meta_extracts_stars_from_star_name():
    svc = _make_service(
        {
            "date": "2026-08-01",
            "img": "https://javbus.com/a.jpg",
            "url": "https://javbus.com/x",
            "title": "T",
            "star_name": "三上悠亜",
        }
    )
    work = svc.get_av_meta("SSIS-123")
    assert work.stars == ["三上悠亜"]


def test_meta_extracts_stars_list():
    svc = _make_service({"date": "", "img": "", "url": "", "title": "", "stars": ["A", "B"]})
    work = svc.get_av_meta("SSIS-123")
    assert work.stars == ["A", "B"]


def test_meta_no_stars():
    svc = _make_service({"date": "", "img": "", "url": "", "title": ""})
    work = svc.get_av_meta("SSIS-123")
    assert work.stars == []
