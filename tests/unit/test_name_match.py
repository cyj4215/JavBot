import pytest
from unittest.mock import Mock

from app.services.name_match_service import NameMatchService  # noqa: E402
from app.services.text_utils import contains_cjk, normalize_name


class TestTextUtils:
    def test_normalize_name(self):
        assert normalize_name("  三上悠亜  ") == "三上悠亜"

    def test_contains_cjk_true(self):
        assert contains_cjk("三上悠亜")
        assert contains_cjk("hello 世界")

    def test_contains_cjk_false(self):
        assert not contains_cjk("hello world")
        assert not contains_cjk("12345")

    def test_default_alias_map(self):
        m = NameMatchService._default_alias_map()
        assert m["三上悠亚"] == "三上悠亜"
        assert m["苍井空"] == "蒼井そら"
        assert "河北彩花" in m


class TestNameCandidates:
    @pytest.fixture
    def svc(self):
        javbus = Mock()
        limiter = Mock()
        s2t = Mock()
        s2t.convert = Mock(side_effect=lambda x: x)
        t2s = Mock()
        t2s.convert = Mock(side_effect=lambda x: x)
        return NameMatchService(
            javbus_util=javbus,
            s2t=s2t,
            t2s=t2s,
            javbus_limiter=limiter,
        )

    def test_alias_map_lookup(self, svc):
        candidates = svc.name_candidates("三上悠亚")
        assert "三上悠亜" in candidates

    def test_normalize_in_candidates(self, svc):
        candidates = svc.name_candidates("  TEST  ")
        assert any(c == "TEST" for c in candidates)

    def test_cjk_generates_variants(self, svc):
        candidates = svc.name_candidates("三上悠亜")
        assert "三上悠亜" in candidates
        assert any(c == "san shang you ya" or "san" in c for c in candidates)
