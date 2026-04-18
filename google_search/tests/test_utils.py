"""Tests for SERP utility functions."""

from google_search.utils import (
    clean_url,
    parse_result_count,
    parse_search_time,
    strip_tracking_params,
)


class TestCleanUrl:
    def test_google_redirect_with_q(self):
        url = "/url?q=https://example.com/page&sa=U&ved=2ahUKE"
        assert clean_url(url) == "https://example.com/page"

    def test_google_full_redirect(self):
        url = "https://www.google.com/url?q=https://example.com&sa=t"
        assert clean_url(url) == "https://example.com"

    def test_google_redirect_with_url_param(self):
        url = "https://www.google.com/url?url=https://example.com/path"
        assert clean_url(url) == "https://example.com/path"

    def test_clean_url_passthrough(self):
        url = "https://example.com/page"
        assert clean_url(url) == "https://example.com/page"

    def test_empty_string(self):
        assert clean_url("") == ""

    def test_encoded_url(self):
        url = "/url?q=https%3A%2F%2Fexample.com%2Fpath%3Fid%3D123&sa=U"
        assert clean_url(url) == "https://example.com/path?id=123"


class TestParseResultCount:
    def test_standard_format(self):
        assert parse_result_count("About 1,234,000 results (0.52 seconds)") == 1234000

    def test_small_count(self):
        assert parse_result_count("3 results (0.1 seconds)") == 3

    def test_no_about_prefix(self):
        assert parse_result_count("1,000 results (0.3 seconds)") == 1000

    def test_empty_string(self):
        assert parse_result_count("") is None

    def test_no_results_text(self):
        assert parse_result_count("No results found") is None


class TestParseSearchTime:
    def test_standard_format(self):
        assert parse_search_time("About 1,234,000 results (0.52 seconds)") == 0.52

    def test_comma_decimal(self):
        assert parse_search_time("results (0,45 seconds)") == 0.45

    def test_empty_string(self):
        assert parse_search_time("") is None

    def test_no_time_present(self):
        assert parse_search_time("About 1000 results") is None


class TestStripTrackingParams:
    def test_removes_utm_params(self):
        url = "https://example.com/page?utm_source=google&id=123"
        result = strip_tracking_params(url)
        assert "utm_source" not in result
        assert "id=123" in result

    def test_removes_gclid(self):
        url = "https://example.com/?gclid=abc123&page=2"
        result = strip_tracking_params(url)
        assert "gclid" not in result
        assert "page=2" in result

    def test_preserves_clean_url(self):
        url = "https://example.com/page?id=123&type=article"
        assert strip_tracking_params(url) == url

    def test_empty_string(self):
        assert strip_tracking_params("") == ""

    def test_url_without_params(self):
        url = "https://example.com/page"
        assert strip_tracking_params(url) == url

    def test_all_tracking_removed(self):
        url = "https://example.com/page?utm_source=google&utm_medium=cpc"
        result = strip_tracking_params(url)
        assert result == "https://example.com/page"
