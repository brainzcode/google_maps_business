"""Tests for google_maps.config — ScraperConfig."""

import os
import tempfile

import pytest

from google_maps.config import ScraperConfig


class TestScraperConfig:
    def test_defaults(self):
        c = ScraperConfig()
        assert c.max_results == 100
        assert c.headless is True
        assert c.locale == "en"
        assert c.proxy is None
        assert c.proxies == ()
        assert c.proxy_file is None
        assert c.proxy_rotation == "sticky"
        assert c.proxy_max_failures == 3
        assert c.proxy_cooldown_sec == 300.0
        assert c.max_retries == 3
        assert c.output_format == "all"
        assert c.zoom == 14

    def test_frozen(self):
        c = ScraperConfig()
        with pytest.raises(AttributeError):
            c.max_results = 50

    def test_queries_from_query(self):
        c = ScraperConfig(query="plumbers in Chicago")
        assert c.queries() == ["plumbers in Chicago"]

    def test_queries_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("query one\n\nquery two\n  \nquery three\n")
            f.flush()
            path = f.name
        try:
            c = ScraperConfig(input_file=path)
            assert c.queries() == ["query one", "query two", "query three"]
        finally:
            os.unlink(path)

    def test_queries_file_with_comments(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# this is a comment\nreal query\nsome query # trailing comment\n")
            path = f.name
        try:
            c = ScraperConfig(input_file=path)
            assert c.queries() == ["real query", "some query"]
        finally:
            os.unlink(path)

    def test_queries_file_missing_raises(self):
        c = ScraperConfig(input_file="/nonexistent/queries.txt")
        with pytest.raises(FileNotFoundError):
            c.queries()

    def test_queries_unicode(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("café in München\n寿司 in 東京\n")
            path = f.name
        try:
            c = ScraperConfig(input_file=path)
            assert c.queries() == ["café in München", "寿司 in 東京"]
        finally:
            os.unlink(path)

    def test_queries_empty(self):
        c = ScraperConfig()
        assert c.queries() == []

    def test_query_takes_precedence_over_file(self):
        c = ScraperConfig(query="direct query", input_file="nonexistent.txt")
        assert c.queries() == ["direct query"]

    def test_user_agents_not_empty(self):
        c = ScraperConfig()
        assert len(c.user_agents) > 0
        for ua in c.user_agents:
            assert "Mozilla" in ua

    def test_timing_defaults_are_sane(self):
        c = ScraperConfig()
        assert c.min_action_delay < c.max_action_delay
        assert c.scroll_delay_min < c.scroll_delay_max
        assert c.retry_base_delay < c.retry_max_delay


class TestProxyStrings:
    def test_empty_by_default(self):
        assert ScraperConfig().proxy_strings() == []

    def test_single_proxy_only(self):
        c = ScraperConfig(proxy="1.2.3.4:8080")
        assert c.proxy_strings() == ["1.2.3.4:8080"]

    def test_inline_proxies(self):
        c = ScraperConfig(proxies=("1.2.3.4:8080", "5.6.7.8:3128"))
        assert c.proxy_strings() == ["1.2.3.4:8080", "5.6.7.8:3128"]

    def test_merge_all_sources(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("9.9.9.9:1234\n# comment\n\n")
            path = f.name
        try:
            c = ScraperConfig(
                proxy_file=path,
                proxies=("1.2.3.4:8080",),
                proxy=" 5.6.7.8:3128",
            )
            out = c.proxy_strings()
            # file first, then inline, then single — with dedup
            assert out == ["9.9.9.9:1234", "1.2.3.4:8080", " 5.6.7.8:3128"]
        finally:
            os.unlink(path)

    def test_proxy_strings_dedups(self):
        c = ScraperConfig(
            proxies=("1.2.3.4:8080", "1.2.3.4:8080", "5.6.7.8:3128"),
            proxy="1.2.3.4:8080",
        )
        assert c.proxy_strings() == ["1.2.3.4:8080", "5.6.7.8:3128"]

    def test_proxy_file_missing_raises(self):
        c = ScraperConfig(proxy_file="/nonexistent/proxies.txt")
        with pytest.raises(FileNotFoundError):
            c.proxy_strings()

    def test_proxy_file_with_comments(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# header\n1.2.3.4:8080\n2.3.4.5:8080 # inline comment\n")
            path = f.name
        try:
            c = ScraperConfig(proxy_file=path)
            assert c.proxy_strings() == ["1.2.3.4:8080", "2.3.4.5:8080"]
        finally:
            os.unlink(path)
