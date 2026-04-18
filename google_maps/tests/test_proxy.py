"""Tests for google_maps.proxy — Proxy, parse_proxy_string, ProxyPool."""

from __future__ import annotations

import os
import random
import tempfile

import pytest

from google_maps.proxy import (
    Proxy,
    ProxyPool,
    ROTATION_STRATEGIES,
    load_proxy_file,
    parse_proxy_string,
)


# ── Proxy dataclass ─────────────────────────────────────────────────────────

class TestProxy:
    def test_as_playwright_dict_no_auth(self):
        p = Proxy("http://1.2.3.4:8080")
        assert p.as_playwright_dict() == {"server": "http://1.2.3.4:8080"}

    def test_as_playwright_dict_with_auth(self):
        p = Proxy("http://1.2.3.4:8080", username="u", password="p")
        assert p.as_playwright_dict() == {
            "server": "http://1.2.3.4:8080",
            "username": "u",
            "password": "p",
        }

    def test_host_port_strips_scheme(self):
        p = Proxy("http://1.2.3.4:8080")
        assert p.host_port == "1.2.3.4:8080"

    def test_str_hides_credentials(self):
        p = Proxy("http://1.2.3.4:8080", username="secret", password="secret")
        assert "secret" not in str(p)
        assert str(p) == "1.2.3.4:8080"

    def test_frozen(self):
        p = Proxy("http://1.2.3.4:8080")
        with pytest.raises(AttributeError):
            p.server = "changed"


# ── parse_proxy_string ──────────────────────────────────────────────────────

class TestParseProxyString:
    def test_host_port_only(self):
        p = parse_proxy_string("1.2.3.4:8080")
        assert p.server == "http://1.2.3.4:8080"
        assert p.username is None
        assert p.password is None

    def test_with_scheme(self):
        p = parse_proxy_string("socks5://1.2.3.4:1080")
        assert p.server == "socks5://1.2.3.4:1080"

    def test_userpass_at_host(self):
        p = parse_proxy_string("user:pass@1.2.3.4:8080")
        assert p.server == "http://1.2.3.4:8080"
        assert p.username == "user"
        assert p.password == "pass"

    def test_full_url(self):
        p = parse_proxy_string("http://user:pass@1.2.3.4:8080")
        assert p.server == "http://1.2.3.4:8080"
        assert p.username == "user"
        assert p.password == "pass"

    def test_https_scheme(self):
        p = parse_proxy_string("https://user:pass@proxy.example.com:443")
        assert p.server == "https://proxy.example.com:443"

    def test_colon_separated_legacy(self):
        p = parse_proxy_string("1.2.3.4:8080:user:pass")
        assert p.server == "http://1.2.3.4:8080"
        assert p.username == "user"
        assert p.password == "pass"

    def test_colon_separated_with_scheme(self):
        p = parse_proxy_string("socks5://1.2.3.4:1080")
        assert p.server == "socks5://1.2.3.4:1080"

    def test_url_encoded_credentials(self):
        # %40 = @, %3A = :
        p = parse_proxy_string("http://us%40er:p%3Aass@1.2.3.4:8080")
        assert p.username == "us@er"
        assert p.password == "p:ass"

    def test_strips_surrounding_quotes(self):
        p = parse_proxy_string('"1.2.3.4:8080"')
        assert p.server == "http://1.2.3.4:8080"

    def test_strips_whitespace(self):
        p = parse_proxy_string("   1.2.3.4:8080\n")
        assert p.host_port == "1.2.3.4:8080"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_proxy_string("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_proxy_string("   ")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            parse_proxy_string(None)  # type: ignore[arg-type]

    def test_bad_scheme_raises(self):
        with pytest.raises(ValueError, match="unsupported proxy scheme"):
            parse_proxy_string("ftp://1.2.3.4:8080")

    def test_missing_port_raises(self):
        with pytest.raises(ValueError, match="missing port"):
            parse_proxy_string("1.2.3.4")

    def test_missing_host_raises(self):
        with pytest.raises(ValueError, match="missing host"):
            parse_proxy_string(":8080")

    def test_non_numeric_port_raises(self):
        with pytest.raises(ValueError, match="port not numeric"):
            parse_proxy_string("host:abc")

    def test_port_out_of_range_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            parse_proxy_string("host:99999")

    def test_port_zero_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            parse_proxy_string("host:0")

    def test_username_only(self):
        p = parse_proxy_string("user@1.2.3.4:8080")
        assert p.username == "user"
        assert p.password == ""


# ── load_proxy_file ─────────────────────────────────────────────────────────

class TestLoadProxyFile:
    def test_basic_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("1.2.3.4:8080\n5.6.7.8:3128\n")
            path = f.name
        try:
            proxies = load_proxy_file(path)
            assert len(proxies) == 2
            assert proxies[0].host_port == "1.2.3.4:8080"
        finally:
            os.unlink(path)

    def test_skips_blanks_and_comments(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("# a comment\n\n1.2.3.4:8080\n  # indented comment\n5.6.7.8:3128 # trailing\n")
            path = f.name
        try:
            proxies = load_proxy_file(path)
            assert len(proxies) == 2
        finally:
            os.unlink(path)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_proxy_file("/nonexistent/path/proxies.txt")

    def test_malformed_line_reports_line_number(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("1.2.3.4:8080\ngarbage_no_port\n")
            path = f.name
        try:
            with pytest.raises(ValueError, match=":2:"):
                load_proxy_file(path)
        finally:
            os.unlink(path)


# ── ProxyPool ───────────────────────────────────────────────────────────────

@pytest.fixture
def three_proxies():
    return [
        Proxy("http://a:1111"),
        Proxy("http://b:2222"),
        Proxy("http://c:3333"),
    ]


class TestProxyPool:
    def test_requires_proxies(self):
        with pytest.raises(ValueError, match="at least one proxy"):
            ProxyPool([])

    def test_invalid_strategy_raises(self, three_proxies):
        with pytest.raises(ValueError, match="unknown rotation strategy"):
            ProxyPool(three_proxies, strategy="bogus")

    def test_strategies_constant(self):
        assert set(ROTATION_STRATEGIES) == {"round_robin", "random", "sticky"}

    def test_size_and_len(self, three_proxies):
        pool = ProxyPool(three_proxies)
        assert pool.size == 3
        assert len(pool) == 3

    def test_round_robin(self, three_proxies):
        pool = ProxyPool(three_proxies, strategy="round_robin")
        seq = [pool.next() for _ in range(6)]
        assert [p.host_port for p in seq] == [
            "a:1111", "b:2222", "c:3333",
            "a:1111", "b:2222", "c:3333",
        ]

    def test_random_with_seeded_rng(self, three_proxies):
        pool = ProxyPool(three_proxies, strategy="random", rng=random.Random(42))
        seq = [pool.next().host_port for _ in range(5)]
        # Seeded RNG makes this deterministic
        assert all(h in {"a:1111", "b:2222", "c:3333"} for h in seq)

    def test_sticky_holds_until_bad(self, three_proxies):
        pool = ProxyPool(three_proxies, strategy="sticky")
        p1 = pool.next()
        p2 = pool.next()
        assert p1 == p2  # sticky returns the same proxy
        pool.mark_bad(p1, "test")
        p3 = pool.next()
        assert p3 != p1

    def test_mark_bad_cooldown(self, three_proxies):
        pool = ProxyPool(three_proxies, strategy="round_robin", max_failures=2, cooldown_sec=100)
        target = three_proxies[0]
        pool.mark_bad(target)
        pool.mark_bad(target)  # hits threshold
        status = {s["proxy"]: s for s in pool.status()}
        assert status["a:1111"]["cooldown_remaining"] > 0

    def test_mark_good_resets(self, three_proxies):
        pool = ProxyPool(three_proxies, max_failures=2, cooldown_sec=100)
        target = three_proxies[0]
        pool.mark_bad(target)
        pool.mark_good(target)
        status = {s["proxy"]: s for s in pool.status()}
        assert status["a:1111"]["failures"] == 0
        assert status["a:1111"]["cooldown_remaining"] == 0

    def test_all_in_cooldown_still_returns_one(self, three_proxies):
        pool = ProxyPool(three_proxies, max_failures=1, cooldown_sec=100)
        for p in three_proxies:
            pool.mark_bad(p)
        # All are in cooldown but .next() must not block
        out = pool.next()
        assert out in three_proxies

    def test_healthy_excludes_cooldown(self, three_proxies):
        pool = ProxyPool(three_proxies, max_failures=1, cooldown_sec=100)
        pool.mark_bad(three_proxies[0])
        healthy = pool.healthy()
        assert three_proxies[0] not in healthy
        assert len(healthy) == 2

    def test_cooldown_expires(self, three_proxies, monkeypatch):
        pool = ProxyPool(three_proxies, max_failures=1, cooldown_sec=10)
        # Freeze then advance `now`
        t = [1000.0]
        pool._now = lambda: t[0]
        pool.mark_bad(three_proxies[0])
        assert three_proxies[0] not in pool.healthy()
        t[0] += 11  # cooldown expires
        assert three_proxies[0] in pool.healthy()

    def test_mark_bad_unknown_proxy_no_raise(self, three_proxies):
        pool = ProxyPool(three_proxies)
        # Proxy not in the pool — should be a silent no-op
        pool.mark_bad(Proxy("http://z:9999"))

    def test_mark_good_unknown_proxy_no_raise(self, three_proxies):
        pool = ProxyPool(three_proxies)
        pool.mark_good(Proxy("http://z:9999"))

    def test_from_strings(self):
        pool = ProxyPool.from_strings(["1.2.3.4:8080", "5.6.7.8:3128", ""])
        assert pool.size == 2

    def test_from_strings_propagates_parse_errors(self):
        with pytest.raises(ValueError):
            ProxyPool.from_strings(["garbage_no_port"])

    def test_max_failures_floor(self, three_proxies):
        pool = ProxyPool(three_proxies, max_failures=0)
        assert pool.max_failures == 1  # floor at 1

    def test_cooldown_floor(self, three_proxies):
        pool = ProxyPool(three_proxies, cooldown_sec=-10)
        assert pool.cooldown_sec == 0.0

    def test_status_snapshot_shape(self, three_proxies):
        pool = ProxyPool(three_proxies)
        snap = pool.status()
        assert len(snap) == 3
        for s in snap:
            assert set(s.keys()) == {"proxy", "failures", "cooldown_remaining"}

    def test_sticky_rotates_after_mark_bad(self, three_proxies):
        pool = ProxyPool(three_proxies, strategy="sticky", max_failures=10)
        p1 = pool.next()
        pool.mark_bad(p1)  # below threshold, no cooldown, but sticky should move on
        p2 = pool.next()
        assert p2 != p1

    def test_same_server_distinct_usernames(self):
        proxies = [
            Proxy("http://a:1111", username="u1"),
            Proxy("http://a:1111", username="u2"),
        ]
        pool = ProxyPool(proxies, strategy="round_robin")
        pool.mark_bad(proxies[0])
        # Only the first entry's health should be affected
        snap = {s["proxy"] + str(i): s for i, s in enumerate(pool.status())}
        # Can't fully verify by proxy key because host_port is identical —
        # check the failure count distribution instead
        counts = [s["failures"] for s in pool.status()]
        assert counts == [1, 0]
