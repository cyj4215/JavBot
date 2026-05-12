import time
import pytest
from app.cache import TTLCache


class TestTTLCache:
    def test_set_and_get(self):
        c = TTLCache(max_size=100, default_ttl=600)
        c.set("a", 1)
        assert c.get("a") == 1
        assert c.get("b") is None

    def test_expiry(self):
        c = TTLCache(max_size=100, default_ttl=30)
        c.set("a", 1, ttl=1)
        assert c.get("a") == 1
        time.sleep(1.5)
        assert c.get("a") is None

    def test_custom_ttl(self):
        c = TTLCache(max_size=100, default_ttl=600)
        c.set("a", 1, ttl=0)
        time.sleep(0.1)
        assert c.get("a") is None

    def test_max_size_eviction(self):
        c = TTLCache(max_size=64, default_ttl=600)
        for i in range(65):
            c.set(i, i)
        assert c.get(0) is None

    def test_update_existing_moves_to_end(self):
        c = TTLCache(max_size=64, default_ttl=600)
        c.set("a", 1)
        c.set("b", 2)
        for i in range(62):
            c.set(i, i)
        # cache is full (64 items), a is oldest, b is second oldest
        c.get("a")  # a moves to newest
        c.set("new", 99)  # evicts b (now the oldest)
        assert c.get("a") == 1
        assert c.get("b") is None
        assert c.get("new") == 99

    def test_contains(self):
        c = TTLCache(max_size=100, default_ttl=600)
        c.set("a", 1)
        assert "a" in c
        assert "b" not in c

    def test_getitem_and_setitem(self):
        c = TTLCache(max_size=100, default_ttl=600)
        c["a"] = 1
        assert c["a"] == 1
        with pytest.raises(KeyError):
            c["b"]

    def test_len(self):
        c = TTLCache(max_size=100, default_ttl=600)
        assert len(c) == 0
        c.set("a", 1)
        c.set("b", 2)
        assert len(c) == 2

    def test_min_limits_enforced(self):
        c = TTLCache(max_size=0, default_ttl=0)
        assert c.max_size == 64
        assert c.default_ttl == 30
