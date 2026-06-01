"""Tests for javdb_scraper: avatar URL handling."""
import pytest

from app.services.javdb_scraper import _parse_actor_search


class TestParseActorSearchAvatarUrl:
    def test_absolute_url_unchanged(self):
        html = """
        <div class="actor-box">
          <a href="/actors/abc"><strong>三上悠亜</strong></a>
          <img class="avatar" src="https://javdb.com/actors/avatar/xxx.jpg">
        </div>
        """
        actors = _parse_actor_search(html)
        assert len(actors) == 1
        assert actors[0]["avatar"] == "https://javdb.com/actors/avatar/xxx.jpg"

    def test_relative_url_made_absolute(self):
        html = """
        <div class="actor-box">
          <a href="/actors/abc"><strong>三上悠亜</strong></a>
          <img class="avatar" src="/uploads/actor/avatar/yyy.jpg">
        </div>
        """
        actors = _parse_actor_search(html)
        assert len(actors) == 1
        assert actors[0]["avatar"] == "https://javdb.com/uploads/actor/avatar/yyy.jpg"

    def test_data_src_fallback(self):
        html = """
        <div class="actor-box">
          <a href="/actors/abc"><strong>Test</strong></a>
          <img class="avatar" data-src="/uploads/actor/avatar/zzz.jpg">
        </div>
        """
        actors = _parse_actor_search(html)
        assert len(actors) == 1
        assert actors[0]["avatar"] == "https://javdb.com/uploads/actor/avatar/zzz.jpg"

    def test_no_img_tag(self):
        html = """
        <div class="actor-box">
          <a href="/actors/abc"><strong>No Image</strong></a>
        </div>
        """
        actors = _parse_actor_search(html)
        assert len(actors) == 1
        assert actors[0]["avatar"] == ""

    def test_empty_result(self):
        html = "<html><body>No actors</body></html>"
        actors = _parse_actor_search(html)
        assert actors == []

    def test_cloudflare_challenge(self):
        html = "<html><head><title>Cloudflare Challenge</title></head><body></body></html>"
        actors = _parse_actor_search(html)
        assert actors == []

    def test_multiple_actors(self):
        html = """
        <div class="actor-box">
          <a href="/a1"><strong>Actress A</strong></a>
          <img src="https://javdb.com/avatar/a.jpg">
        </div>
        <div class="actor-box">
          <a href="/a2"><strong>Actress B</strong></a>
          <img src="/uploads/avatar/b.jpg">
        </div>
        """
        actors = _parse_actor_search(html)
        assert len(actors) == 2
        assert actors[0]["avatar"] == "https://javdb.com/avatar/a.jpg"
        assert actors[1]["avatar"] == "https://javdb.com/uploads/avatar/b.jpg"
