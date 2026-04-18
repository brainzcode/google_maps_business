"""Tests for google_maps.utils — URL parsing, filenames, delays, parsers."""

import pytest

from google_maps.utils import (
    coords_from_url,
    clean_filename,
    build_maps_url,
    human_delay,
    parse_review_count,
    parse_rating,
    parse_price_level,
)


# ── coords_from_url ─────────────────────────────────────────────────────────

class TestCoordsFromUrl:
    def test_standard_url(self):
        url = "https://www.google.com/maps/place/Some+Place/@41.8781,-87.6298,14z/data=!3m1"
        assert coords_from_url(url) == (41.8781, -87.6298)

    def test_negative_coordinates(self):
        url = "https://www.google.com/maps/@-33.8688,151.2093,15z"
        assert coords_from_url(url) == (-33.8688, 151.2093)

    def test_no_coordinates(self):
        assert coords_from_url("https://www.google.com/maps") == (None, None)

    def test_empty_string(self):
        assert coords_from_url("") == (None, None)

    def test_partial_url(self):
        assert coords_from_url("https://example.com/@notcoords") == (None, None)

    def test_high_precision(self):
        url = "https://www.google.com/maps/@41.87812345,-87.62983456,14z"
        lat, lng = coords_from_url(url)
        assert abs(lat - 41.87812345) < 1e-8
        assert abs(lng - (-87.62983456)) < 1e-8

    def test_integer_coordinates(self):
        url = "https://www.google.com/maps/@41,-87,14z"
        assert coords_from_url(url) == (41.0, -87.0)

    def test_none_url(self):
        assert coords_from_url(None) == (None, None)  # type: ignore[arg-type]


# ── clean_filename ───────────────────────────────────────────────────────────

class TestCleanFilename:
    def test_basic(self):
        assert clean_filename("plumbers in Chicago") == "plumbers_in_Chicago"

    def test_special_characters(self):
        result = clean_filename("café & bar! @#$%")
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result

    def test_empty_string(self):
        assert clean_filename("") == "untitled"

    def test_whitespace_only(self):
        assert clean_filename("   ") == "untitled"

    def test_max_length(self):
        long = "a" * 200
        assert len(clean_filename(long)) == 100

    def test_custom_max_length(self):
        long = "a" * 200
        assert len(clean_filename(long, max_len=50)) == 50

    def test_leading_trailing_underscores_stripped(self):
        result = clean_filename("  !hello!  ")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_hyphens_preserved(self):
        assert "test-file" in clean_filename("test-file")


# ── build_maps_url ───────────────────────────────────────────────────────────

class TestBuildMapsUrl:
    def test_with_center(self):
        url = build_maps_url("41.88,-87.63", 14)
        assert url == "https://www.google.com/maps/@41.88,-87.63,14z"

    def test_without_center(self):
        assert build_maps_url(None, 14) == "https://www.google.com/maps"

    def test_bad_center(self):
        assert build_maps_url("bad", 14) == "https://www.google.com/maps"

    def test_single_value_center(self):
        assert build_maps_url("41.88", 14) == "https://www.google.com/maps"

    def test_spaces_in_center(self):
        url = build_maps_url("41.88, -87.63", 14)
        assert url == "https://www.google.com/maps/@41.88,-87.63,14z"

    def test_different_zoom(self):
        url = build_maps_url("40.71,-74.00", 18)
        assert "18z" in url

    def test_zoom_clamped_high(self):
        url = build_maps_url("40.71,-74.00", 99)
        assert "21z" in url

    def test_zoom_clamped_low(self):
        url = build_maps_url("40.71,-74.00", -5)
        assert "1z" in url

    def test_rejects_out_of_range_lat(self):
        # lat > 90 falls back to the no-center URL
        assert build_maps_url("100,0", 14) == "https://www.google.com/maps"

    def test_rejects_out_of_range_lng(self):
        assert build_maps_url("0,-200", 14) == "https://www.google.com/maps"

    def test_rejects_three_values(self):
        assert build_maps_url("1,2,3", 14) == "https://www.google.com/maps"


# ── human_delay ──────────────────────────────────────────────────────────────

class TestHumanDelay:
    def test_within_bounds(self):
        for _ in range(100):
            d = human_delay(400, 1200)
            assert 400 <= d <= 1200

    def test_different_ranges(self):
        for _ in range(50):
            d = human_delay(100, 200)
            assert 100 <= d <= 200

    def test_returns_int(self):
        assert isinstance(human_delay(100, 500), int)

    def test_equal_bounds_returns_value(self):
        assert human_delay(500, 500) == 500

    def test_swapped_bounds_normalised(self):
        # Even when the user passes (max, min), result stays in range
        for _ in range(30):
            d = human_delay(800, 400)
            assert 400 <= d <= 800


# ── parse_review_count ───────────────────────────────────────────────────────

class TestParseReviewCount:
    def test_parenthesised(self):
        assert parse_review_count("(1,234)") == 1234

    def test_with_text(self):
        assert parse_review_count("892 reviews") == 892

    def test_plain_number(self):
        assert parse_review_count("42") == 42

    def test_empty(self):
        assert parse_review_count("") is None

    def test_no_digits(self):
        assert parse_review_count("no reviews") is None

    def test_large_number(self):
        assert parse_review_count("12,345 reviews") == 12345

    def test_bare_comma_returns_none(self):
        assert parse_review_count(",") is None

    def test_none_input(self):
        assert parse_review_count(None) is None  # type: ignore[arg-type]


# ── parse_rating ─────────────────────────────────────────────────────────────

class TestParseRating:
    def test_english(self):
        assert parse_rating("4.5 stars") == 4.5

    def test_comma_decimal(self):
        assert parse_rating("3,8 Sterne") == 3.8

    def test_integer(self):
        assert parse_rating("5 stars") == 5.0

    def test_empty(self):
        assert parse_rating("") is None

    def test_no_number(self):
        assert parse_rating("stars") is None

    def test_none_input(self):
        assert parse_rating(None) is None  # type: ignore[arg-type]

    def test_embedded_in_prose(self):
        assert parse_rating("Rated 4.7 out of 5 based on 12 reviews") == 4.7


# ── parse_price_level ────────────────────────────────────────────────────────

class TestParsePriceLevel:
    def test_dollars(self):
        assert parse_price_level("Price: $$$") == "$$$"

    def test_pounds(self):
        assert parse_price_level("Price: ££") == "££"

    def test_euros(self):
        assert parse_price_level("Price: €€€€") == "€€€€"

    def test_no_symbol(self):
        assert parse_price_level("Price: Moderate") == ""

    def test_empty(self):
        assert parse_price_level("") == ""

    def test_yen(self):
        assert parse_price_level("Price: ¥¥") == "¥¥"

    def test_none_input(self):
        assert parse_price_level(None) == ""  # type: ignore[arg-type]
