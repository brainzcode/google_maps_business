"""Tests for SerpConfig."""

import os
import tempfile
import pytest

from google_search.config import SerpConfig


class TestSerpConfigDefaults:
    def test_default_values(self):
        config = SerpConfig()
        assert config.query == ""
        assert config.input_file == ""
        assert config.max_pages == 1
        assert config.results_per_page == 10
        assert config.output_dir == "output"
        assert config.output_format == "all"
        assert config.headless is True
        assert config.locale == "en"
        assert config.proxy is None
        assert config.timeout_ms == 60_000
        assert config.block_resources is True
        assert config.max_retries == 3
        assert config.extract_organic is True
        assert config.extract_ads is True

    def test_frozen_immutability(self):
        config = SerpConfig()
        with pytest.raises(AttributeError):
            config.query = "test"

    def test_user_agents_populated(self):
        config = SerpConfig()
        assert len(config.user_agents) == 5
        for ua in config.user_agents:
            assert "Mozilla" in ua


class TestSerpConfigQueries:
    def test_single_query(self):
        config = SerpConfig(query="test search")
        assert config.queries() == ["test search"]

    def test_query_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("query one\nquery two\n\nquery three\n")
            f.flush()
            config = SerpConfig(input_file=f.name)
            queries = config.queries()
            os.unlink(f.name)

        assert queries == ["query one", "query two", "query three"]

    def test_empty_queries(self):
        config = SerpConfig()
        assert config.queries() == []

    def test_query_takes_precedence_over_file(self):
        config = SerpConfig(query="direct query", input_file="nonexistent.txt")
        assert config.queries() == ["direct query"]


class TestBuildSearchUrl:
    def test_basic_url(self):
        config = SerpConfig()
        url = config.build_search_url("test query")
        assert url == "https://www.google.com/search?q=test+query"

    def test_url_with_pagination(self):
        config = SerpConfig()
        url = config.build_search_url("test", page=2)
        assert "start=20" in url

    def test_url_with_custom_num(self):
        config = SerpConfig(results_per_page=20)
        url = config.build_search_url("test", page=1)
        assert "num=20" in url
        assert "start=20" in url

    def test_url_with_country_and_language(self):
        config = SerpConfig(country="us", language="en")
        url = config.build_search_url("test")
        assert "gl=us" in url
        assert "hl=en" in url

    def test_url_with_safe_search(self):
        config = SerpConfig(safe_search=True)
        url = config.build_search_url("test")
        assert "safe=active" in url

    def test_url_page_zero_no_start(self):
        config = SerpConfig()
        url = config.build_search_url("test", page=0)
        assert "start=" not in url

    def test_url_encodes_special_characters(self):
        config = SerpConfig()
        url = config.build_search_url("python & java")
        assert "python+%26+java" in url

    def test_default_num_not_in_url(self):
        config = SerpConfig(results_per_page=10)
        url = config.build_search_url("test")
        assert "num=" not in url
