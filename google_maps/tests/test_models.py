"""Tests for google_maps.models — Business and BusinessList."""

import pytest

from google_maps.models import Business, BusinessList


# ── Business ─────────────────────────────────────────────────────────────────

class TestBusiness:
    def test_default_fields(self):
        b = Business()
        assert b.name == ""
        assert b.rating is None
        assert b.reviews is None

    def test_is_valid_with_name(self):
        b = Business(name="Joe's Pizza")
        assert b.is_valid is True

    def test_is_valid_empty_name(self):
        b = Business(name="")
        assert b.is_valid is False

    def test_is_valid_whitespace_name(self):
        b = Business(name="   ")
        assert b.is_valid is False

    def test_dedup_key_uses_url(self):
        b = Business(name="Test", url="https://maps.google.com/place/test?q=1")
        assert b.dedup_key == "https://maps.google.com/place/test"

    def test_dedup_key_falls_back_to_name(self):
        b = Business(name="Test Place")
        assert b.dedup_key == "Test Place"

    def test_to_dict(self):
        b = Business(name="Acme", phone="555-1234")
        d = b.to_dict()
        assert d["name"] == "Acme"
        assert d["phone"] == "555-1234"
        assert "latitude" in d
        assert isinstance(d, dict)

    def test_to_dict_has_all_fields(self):
        b = Business()
        d = b.to_dict()
        expected_keys = {
            "name", "category", "address", "phone", "website",
            "rating", "reviews", "price_level", "hours", "plus_code",
            "latitude", "longitude", "status", "email", "service_options", "url",
        }
        assert set(d.keys()) == expected_keys


# ── BusinessList ─────────────────────────────────────────────────────────────

class TestBusinessList:
    def test_add_valid(self):
        bl = BusinessList()
        b = Business(name="Pizza Place", url="https://maps.google.com/place/pizza")
        assert bl.add(b) is True
        assert len(bl) == 1

    def test_add_duplicate_rejected(self):
        bl = BusinessList()
        b1 = Business(name="Pizza", url="https://maps.google.com/place/pizza?q=1")
        b2 = Business(name="Pizza", url="https://maps.google.com/place/pizza?q=2")
        assert bl.add(b1) is True
        assert bl.add(b2) is False
        assert len(bl) == 1

    def test_add_invalid_rejected(self):
        bl = BusinessList()
        b = Business(name="")
        assert bl.add(b) is False
        assert len(bl) == 0

    def test_add_whitespace_name_rejected(self):
        bl = BusinessList()
        b = Business(name="   ")
        assert bl.add(b) is False
        assert len(bl) == 0

    def test_different_urls_are_separate(self):
        bl = BusinessList()
        b1 = Business(name="Place A", url="https://maps.google.com/place/a")
        b2 = Business(name="Place B", url="https://maps.google.com/place/b")
        assert bl.add(b1) is True
        assert bl.add(b2) is True
        assert len(bl) == 2

    def test_bool_empty(self):
        bl = BusinessList()
        assert not bl

    def test_bool_with_items(self):
        bl = BusinessList()
        bl.add(Business(name="Test"))
        assert bl

    def test_len(self):
        bl = BusinessList()
        assert len(bl) == 0
        bl.add(Business(name="A"))
        bl.add(Business(name="B"))
        assert len(bl) == 2

    def test_dedup_by_name_when_no_url(self):
        bl = BusinessList()
        b1 = Business(name="Same Name")
        b2 = Business(name="Same Name")
        assert bl.add(b1) is True
        assert bl.add(b2) is False
        assert len(bl) == 1

    def test_same_url_path_different_query_dedups(self):
        bl = BusinessList()
        b1 = Business(name="A", url="https://maps.google.com/place/X?hl=en")
        b2 = Business(name="A", url="https://maps.google.com/place/X?hl=fr")
        bl.add(b1)
        assert bl.add(b2) is False

    def test_iter_via_businesses_attribute(self):
        bl = BusinessList()
        bl.add(Business(name="A"))
        bl.add(Business(name="B"))
        names = [b.name for b in bl.businesses]
        assert names == ["A", "B"]
