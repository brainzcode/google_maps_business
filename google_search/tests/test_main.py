"""Tests for google_search.main — argparse → config wiring, proxy pool, concurrency gating."""

from __future__ import annotations

import argparse

import pytest

from google_search.main import build_config, build_proxy_pool, validate_concurrency


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(
        search="best python frameworks",
        input=None,
        pages=1,
        num=10,
        output="output",
        format="csv",
        headless=True,
        no_block=False,
        country="",
        language="",
        safe=False,
        retries=3,
        organic_only=False,
        concurrency=1,
        proxy=None,
        proxies=None,
        proxy_file=None,
        proxy_username=None,
        proxy_password=None,
        proxy_rotation="sticky",
        proxy_max_failures=3,
        proxy_cooldown=300.0,
        verbose=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestBuildConfig:
    def test_basic(self):
        c = build_config(_args())
        assert c.query == "best python frameworks"
        assert c.max_pages == 1
        assert c.results_per_page == 10
        assert c.concurrency == 1

    def test_pages_capped_at_ten(self):
        c = build_config(_args(pages=99))
        assert c.max_pages == 10

    def test_organic_only_disables_features(self):
        c = build_config(_args(organic_only=True))
        assert c.extract_organic is True
        assert c.extract_ads is False
        assert c.extract_featured_snippet is False
        assert c.extract_local_pack is False

    def test_proxies_inline_csv(self):
        c = build_config(_args(proxies="1.2.3.4:8080, 5.6.7.8:3128 , "))
        assert c.proxies == ("1.2.3.4:8080", "5.6.7.8:3128")

    def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("SERP_PROXY_USERNAME", "envuser")
        monkeypatch.setenv("SERP_PROXY_PASSWORD", "envpass")
        monkeypatch.setenv("SERP_PROXY", "1.2.3.4:8080")
        c = build_config(_args())
        assert c.proxy_username == "envuser"
        assert c.proxy_password == "envpass"
        assert c.proxy == "1.2.3.4:8080"

    def test_cli_overrides_env(self, monkeypatch):
        monkeypatch.setenv("SERP_PROXY_USERNAME", "envuser")
        c = build_config(_args(proxy_username="cliuser"))
        assert c.proxy_username == "cliuser"

    def test_concurrency_floors_at_one(self):
        assert build_config(_args(concurrency=0)).concurrency == 1
        assert build_config(_args(concurrency=-5)).concurrency == 1

    def test_concurrency_passthrough(self):
        assert build_config(_args(concurrency=6)).concurrency == 6


class TestBuildProxyPool:
    def test_returns_none_with_no_proxies(self):
        assert build_proxy_pool(build_config(_args())) is None

    def test_builds_pool(self):
        c = build_config(_args(proxies="1.2.3.4:8080,5.6.7.8:3128"))
        pool = build_proxy_pool(c)
        assert pool is not None
        assert pool.size == 2

    def test_default_credentials_applied(self):
        c = build_config(_args(
            proxies="1.2.3.4:8080",
            proxy_username="u",
            proxy_password="p",
        ))
        pool = build_proxy_pool(c)
        p = pool.next()
        assert p.username == "u"
        assert p.password == "p"

    def test_existing_credentials_not_overwritten(self):
        c = build_config(_args(
            proxies="preset:pw@1.2.3.4:8080",
            proxy_username="default_user",
            proxy_password="default_pw",
        ))
        pool = build_proxy_pool(c)
        p = pool.next()
        assert p.username == "preset"
        assert p.password == "pw"

    def test_concurrency_forces_round_robin(self):
        c = build_config(_args(
            concurrency=3,
            proxies="a:1111,b:2222,c:3333",
            proxy_rotation="sticky",
        ))
        pool = build_proxy_pool(c)
        assert pool.strategy == "round_robin"

    def test_round_robin_rotation_passes_through(self):
        c = build_config(_args(
            proxies="a:1111,b:2222",
            proxy_rotation="round_robin",
        ))
        assert build_proxy_pool(c).strategy == "round_robin"

    def test_per_query_rotation_uses_sticky_underneath(self):
        c = build_config(_args(
            proxies="a:1111,b:2222",
            proxy_rotation="per_query",
        ))
        assert build_proxy_pool(c).strategy == "sticky"


class TestValidateConcurrency:
    def test_serial_no_pool_ok(self):
        validate_concurrency(build_config(_args(concurrency=1)), None)

    def test_concurrent_no_pool_exits(self):
        c = build_config(_args(concurrency=4))
        with pytest.raises(SystemExit) as exc:
            validate_concurrency(c, None)
        assert exc.value.code == 2

    def test_concurrent_pool_too_small_exits(self):
        c = build_config(_args(concurrency=5, proxies="a:1111,b:2222"))
        pool = build_proxy_pool(c)
        with pytest.raises(SystemExit) as exc:
            validate_concurrency(c, pool)
        assert exc.value.code == 2

    def test_concurrent_pool_just_enough_ok(self):
        c = build_config(_args(concurrency=3, proxies="a:1111,b:2222,c:3333"))
        pool = build_proxy_pool(c)
        validate_concurrency(c, pool)

    def test_error_mentions_proxy_flags(self, capsys):
        c = build_config(_args(concurrency=2))
        with pytest.raises(SystemExit):
            validate_concurrency(c, None)
        err = capsys.readouterr().err
        assert "proxy" in err.lower()


class TestQueriesAndProxyStrings:
    def test_queries_empty(self):
        c = build_config(_args(search=""))
        assert c.queries() == []

    def test_proxy_strings_dedup_and_merge(self):
        c = build_config(_args(
            proxies="1.2.3.4:8080,1.2.3.4:8080,5.6.7.8:3128",
            proxy="1.2.3.4:8080",
        ))
        assert c.proxy_strings() == ["1.2.3.4:8080", "5.6.7.8:3128"]

    def test_proxy_file_missing_raises(self):
        c = build_config(_args())
        c2 = c.__class__(**{**c.__dict__, "proxy_file": "/nonexistent/file"})
        with pytest.raises(FileNotFoundError):
            c2.proxy_strings()
