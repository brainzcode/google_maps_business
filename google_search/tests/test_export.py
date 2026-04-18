"""Tests for SERP export functionality."""

import json
import os
import tempfile

import pandas as pd
import pytest

from google_search.export import export_full, export_organic
from google_search.models import (
    OrganicResult,
    PeopleAlsoAskItem,
    RelatedSearch,
    SerpPage,
    SerpResultSet,
)


@pytest.fixture
def sample_results():
    """Create a SerpResultSet with sample data."""
    rs = SerpResultSet()
    page = SerpPage(
        query="test query",
        page_number=0,
        total_results_text="About 1,000 results",
        search_time_text="0.5s",
        organic=[
            OrganicResult(
                position=1,
                title="First Result",
                url="https://example.com/first",
                displayed_url="example.com",
                description="First description",
            ),
            OrganicResult(
                position=2,
                title="Second Result",
                url="https://example.org/second",
                displayed_url="example.org",
                description="Second description",
                date="Jan 15, 2025",
            ),
        ],
        people_also_ask=[
            PeopleAlsoAskItem(question="What is Python?"),
        ],
        related_searches=[
            RelatedSearch(query="related query"),
        ],
    )
    rs.add_page(page)
    return rs


@pytest.fixture
def empty_results():
    return SerpResultSet()


class TestExportOrganic:
    def test_csv_export(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_organic(sample_results, tmpdir, "test", "csv")
            assert len(paths) == 1
            assert paths[0].endswith("_organic.csv")

            df = pd.read_csv(paths[0])
            assert len(df) == 2
            assert "title" in df.columns
            assert "url" in df.columns
            assert "position" in df.columns

    def test_xlsx_export(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_organic(sample_results, tmpdir, "test", "xlsx")
            assert len(paths) == 1
            assert paths[0].endswith("_organic.xlsx")

            df = pd.read_excel(paths[0])
            assert len(df) == 2

    def test_json_export(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_organic(sample_results, tmpdir, "test", "json")
            assert len(paths) == 1
            assert paths[0].endswith("_organic.json")

            with open(paths[0]) as f:
                data = json.loads(f.read())
            assert len(data) == 2
            assert data[0]["title"] == "First Result"

    def test_all_formats(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_organic(sample_results, tmpdir, "test", "all")
            assert len(paths) == 3
            extensions = {os.path.splitext(p)[1] for p in paths}
            assert extensions == {".csv", ".xlsx", ".json"}

    def test_empty_results(self, empty_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_organic(empty_results, tmpdir, "test", "csv")
            assert paths == []

    def test_invalid_format(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="Unsupported format"):
                export_organic(sample_results, tmpdir, "test", "xml")


class TestExportFull:
    def test_full_json_export(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full(sample_results, tmpdir, "test", "json")
            full_json = [p for p in paths if p.endswith("_full.json")]
            assert len(full_json) == 1

            with open(full_json[0]) as f:
                data = json.loads(f.read())
            assert len(data) == 1
            assert data[0]["query"] == "test query"
            assert len(data[0]["organic"]) == 2
            assert len(data[0]["people_also_ask"]) == 1

    def test_full_xlsx_export(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full(sample_results, tmpdir, "test", "xlsx")
            full_xlsx = [p for p in paths if p.endswith("_full.xlsx")]
            assert len(full_xlsx) == 1

            xl = pd.ExcelFile(full_xlsx[0])
            assert "Organic" in xl.sheet_names
            assert "Summary" in xl.sheet_names
            assert "People Also Ask" in xl.sheet_names

    def test_summary_sheet_contents(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full(sample_results, tmpdir, "test", "xlsx")
            full_xlsx = [p for p in paths if p.endswith("_full.xlsx")]

            df = pd.read_excel(full_xlsx[0], sheet_name="Summary")
            assert df.iloc[0]["query"] == "test query"
            assert df.iloc[0]["organic_count"] == 2
            assert df.iloc[0]["paa_count"] == 1

    def test_empty_results(self, empty_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full(empty_results, tmpdir, "test", "all")
            assert paths == []

    def test_creates_output_directory(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "new_dir", "nested")
            paths = export_full(sample_results, output_dir, "test", "csv")
            assert len(paths) > 0
            assert os.path.isdir(output_dir)
