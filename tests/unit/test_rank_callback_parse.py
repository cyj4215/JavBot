"""rank callback 解析：rank: / rank_retry: 统一正则。"""
import re

_PATTERN = re.compile(r"^rank(?:_retry)?:(\d{1,2}):(\d)(?::([01]))?$")


def _parse(data: str):
    m = _PATTERN.match(data)
    if not m:
        return None
    return {
        "limit": int(m.group(1)),
        "page": int(m.group(2)),
        "with_avatars": m.group(3) == "1" if m.group(3) is not None else False,
        "is_retry": data.startswith("rank_retry:"),
    }


def test_rank_normal():
    assert _parse("rank:20:1:0") == {
        "limit": 20, "page": 1, "with_avatars": False, "is_retry": False,
    }


def test_rank_with_avatars():
    assert _parse("rank:20:2:1")["with_avatars"] is True


def test_rank_retry():
    assert _parse("rank_retry:20:3") == {
        "limit": 20, "page": 3, "with_avatars": False, "is_retry": True,
    }


def test_rank_retry_no_avatars_group():
    assert _parse("rank_retry:10:1")["with_avatars"] is False


def test_invalid():
    assert _parse("rank:abc:1") is None
    assert _parse("other:1") is None
