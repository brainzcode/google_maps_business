"""Tests for google_maps.main — argparse → config wiring and proxy pool build."""

from __future__ import annotations

import argparse
import tempfile

import pytest

from google_maps.main import build_config, build_proxy_pool, validate_concurrency


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(
        search="coffee",
        input=None,
        total=50,
        output="output",
        format="csv",
        center=None,
        zoom=14,
        headless=True,
        lang="en",
        concurrency=1,
        proxy=None,
        proxies=None,
        proxy_file=None,
        proxy_username=None,
        proxy_password=None,
        proxy_rotation="sticky",
        proxy_max_failures=3,
        proxy_cooldown=300.0,
        retries=3,
        verbose=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestBuildConfig:
    def test_basic(self):
        c = build_config(_args())
        assert c.query == "coffee"
        assert c.max_results == 50
        assert c.output_format == "csv"

    def test_proxies_inline_csv(self):
        c = build_config(_args(proxies="1.2.3.4:8080, 5.6.7.8:3128 , "))
        assert c.proxies == ("1.2.3.4:8080", "5.6.7.8:3128")

    def test_proxies_empty_csv(self):
        c = build_config(_args(proxies=""))
        assert c.proxies == ()

    def test_env_fallback_for_proxy_credentials(self, monkeypatch):
        monkeypatch.setenv("GMAPS_PROXY_USERNAME", "envuser")
        monkeypatch.setenv("GMAPS_PROXY_PASSWORD", "envpass")
        c = build_config(_args())
        assert c.proxy_username == "envuser"
        assert c.proxy_password == "envpass"

    def test_cli_overrides_env(self, monkeypatch):
        monkeypatch.setenv("GMAPS_PROXY_USERNAME", "envuser")
        c = build_config(_args(proxy_username="cliuser"))
        assert c.proxy_username == "cliuser"

    def test_env_proxy_file(self, monkeypatch):
        monkeypatch.setenv("GMAPS_PROXY_FILE", "/tmp/fake.txt")
        c = build_config(_args())
        assert c.proxy_file == "/tmp/fake.txt"

    def test_env_single_proxy(self, monkeypatch):
        monkeypatch.setenv("GMAPS_PROXY", "1.2.3.4:8080")
        c = build_config(_args())
        assert c.proxy == "1.2.3.4:8080"


class TestBuildProxyPool:
    def test_returns_none_with_no_proxies(self):
        c = build_config(_args())
        assert build_proxy_pool(c) is None

    def test_builds_pool_from_single_proxy(self):
        c = build_config(_args(proxy="1.2.3.4:8080"))
        pool = build_proxy_pool(c)
        assert pool is not None
        assert pool.size == 1

    def test_builds_pool_from_inline_csv(self):
        c = build_config(_args(proxies="1.2.3.4:8080,5.6.7.8:3128"))
        pool = build_proxy_pool(c)
        assert pool is not None
        assert pool.size == 2

    def test_default_credentials_applied_to_unauthed_proxies(self):
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

    def test_per_query_rotation_uses_sticky_underneath(self):
        c = build_config(_args(
            proxies="a:1111,b:2222",
            proxy_rotation="per_query",
        ))
        pool = build_proxy_pool(c)
        assert pool.strategy == "sticky"

    def test_round_robin_rotation_passes_through(self):
        c = build_config(_args(
            proxies="a:1111,b:2222",
            proxy_rotation="round_robin",
        ))
        pool = build_proxy_pool(c)
        assert pool.strategy == "round_robin"

    def test_random_rotation_passes_through(self):
        c = build_config(_args(
            proxies="a:1111,b:2222",
            proxy_rotation="random",
        ))
        pool = build_proxy_pool(c)
        assert pool.strategy == "random"

    def test_proxy_file_is_loaded(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("1.2.3.4:8080\n# comment\n5.6.7.8:3128\n")
            path = f.name
        c = build_config(_args(proxy_file=path))
        pool = build_proxy_pool(c)
        assert pool.size == 2

    def test_bad_proxy_raises(self):
        c = build_config(_args(proxies="garbage_no_port"))
        with pytest.raises(ValueError):
            build_proxy_pool(c)

    def test_concurrency_forces_round_robin(self):
        c = build_config(_args(
            concurrency=3,
            proxies="a:1111,b:2222,c:3333",
            proxy_rotation="sticky",  # user-requested but should be overridden
        ))
        pool = build_proxy_pool(c)
        # With concurrency > 1, pool strategy is forced to round_robin so
        # each worker gets a distinct proxy at startup.
        assert pool.strategy == "round_robin"


class TestValidateConcurrency:
    def test_serial_no_pool_ok(self):
        c = build_config(_args(concurrency=1))
        validate_concurrency(c, None)  # no exit

    def test_serial_with_pool_ok(self):
        c = build_config(_args(concurrency=1, proxies="a:1111"))
        pool = build_proxy_pool(c)
        validate_concurrency(c, pool)

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
        validate_concurrency(c, pool)  # no exit

    def test_concurrent_pool_larger_than_workers_ok(self):
        c = build_config(_args(
            concurrency=2,
            proxies="a:1111,b:2222,c:3333,d:4444",
        ))
        pool = build_proxy_pool(c)
        validate_concurrency(c, pool)

    def test_concurrent_no_pool_error_mentions_proxy_flags(self, capsys):
        c = build_config(_args(concurrency=2))
        with pytest.raises(SystemExit):
            validate_concurrency(c, None)
        err = capsys.readouterr().err
        assert "proxy" in err.lower()

    def test_concurrent_too_small_error_names_counts(self, capsys):
        c = build_config(_args(concurrency=4, proxies="a:1111"))
        pool = build_proxy_pool(c)
        with pytest.raises(SystemExit):
            validate_concurrency(c, pool)
        err = capsys.readouterr().err
        assert "4" in err and "1" in err  # both numbers shown


class TestConfigConcurrency:
    def test_default_is_one(self):
        c = build_config(_args())
        assert c.concurrency == 1

    def test_set_via_cli(self):
        c = build_config(_args(concurrency=8))
        assert c.concurrency == 8

    def test_floors_at_one(self):
        c = build_config(_args(concurrency=0))
        assert c.concurrency == 1

    def test_negative_floors_at_one(self):
        c = build_config(_args(concurrency=-3))
        assert c.concurrency == 1
