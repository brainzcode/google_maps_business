"""Tests for google_maps.export — multi-format file output."""

import json
import os
import tempfile

import pandas as pd
import pytest

from google_maps.export import export, SUPPORTED_FORMATS
from google_maps.models import Business, BusinessList


@pytest.fixture
def sample_results():
    bl = BusinessList()
    bl.add(Business(
        name="Joe's Pizza",
        address="123 Main St",
        phone="555-1234",
        website="https://joespizza.com",
        rating=4.5,
        reviews=892,
    ))
    bl.add(Business(
        name="Pasta Palace",
        address="456 Oak Ave",
        phone="555-5678",
        rating=4.2,
        reviews=340,
    ))
    return bl


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestExport:
    def test_csv_output(self, sample_results, tmp_dir):
        paths = export(sample_results, tmp_dir, "test", "csv")
        assert len(paths) == 1
        assert paths[0].endswith(".csv")
        assert os.path.exists(paths[0])

        df = pd.read_csv(paths[0])
        assert len(df) == 2
        assert "Joe's Pizza" in df["name"].values

    def test_xlsx_output(self, sample_results, tmp_dir):
        paths = export(sample_results, tmp_dir, "test", "xlsx")
        assert len(paths) == 1
        assert paths[0].endswith(".xlsx")
        assert os.path.exists(paths[0])

        df = pd.read_excel(paths[0])
        assert len(df) == 2

    def test_json_output(self, sample_results, tmp_dir):
        paths = export(sample_results, tmp_dir, "test", "json")
        assert len(paths) == 1
        assert paths[0].endswith(".json")

        with open(paths[0]) as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0]["name"] == "Joe's Pizza"

    def test_all_formats(self, sample_results, tmp_dir):
        paths = export(sample_results, tmp_dir, "test", "all")
        assert len(paths) == 3
        extensions = {os.path.splitext(p)[1] for p in paths}
        assert extensions == {".csv", ".xlsx", ".json"}

    def test_empty_results_returns_empty(self, tmp_dir):
        bl = BusinessList()
        paths = export(bl, tmp_dir, "empty", "all")
        assert paths == []

    def test_creates_directory(self, sample_results, tmp_dir):
        nested = os.path.join(tmp_dir, "nested", "dir")
        paths = export(sample_results, nested, "test", "csv")
        assert len(paths) == 1
        assert os.path.isdir(nested)

    def test_invalid_format_raises(self, sample_results, tmp_dir):
        with pytest.raises(ValueError, match="Unsupported format"):
            export(sample_results, tmp_dir, "test", "xml")

    def test_all_fields_in_csv(self, sample_results, tmp_dir):
        paths = export(sample_results, tmp_dir, "test", "csv")
        df = pd.read_csv(paths[0])
        expected_cols = {
            "name", "category", "address", "phone", "website",
            "rating", "reviews", "price_level", "hours", "plus_code",
            "latitude", "longitude", "status", "email", "service_options", "url",
        }
        assert set(df.columns) == expected_cols

    def test_supported_formats_constant(self):
        assert "csv" in SUPPORTED_FORMATS
        assert "xlsx" in SUPPORTED_FORMATS
        assert "json" in SUPPORTED_FORMATS
        assert "all" in SUPPORTED_FORMATS

    def test_json_is_valid_json(self, sample_results, tmp_dir):
        paths = export(sample_results, tmp_dir, "t", "json")
        with open(paths[0]) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert all("name" in row for row in data)

    def test_unicode_in_export(self, tmp_dir):
        bl = BusinessList()
        bl.add(Business(name="東京寿司", address="新宿区"))
        paths = export(bl, tmp_dir, "uni", "json")
        with open(paths[0], encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["name"] == "東京寿司"
