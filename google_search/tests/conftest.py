"""Shared test fixtures for Google SERP scraper tests."""

import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def fixtures_dir():
    """Path to the test fixtures directory."""
    return FIXTURES_DIR


def load_fixture(name: str) -> str:
    """Load an HTML fixture file by name."""
    path = os.path.join(FIXTURES_DIR, name)
    with open(path, "r") as f:
        return f.read()


@pytest.fixture
def organic_html():
    return load_fixture("organic_results.html")


@pytest.fixture
def featured_snippet_html():
    return load_fixture("featured_snippet.html")


@pytest.fixture
def featured_snippet_list_html():
    return load_fixture("featured_snippet_list.html")


@pytest.fixture
def paa_html():
    return load_fixture("people_also_ask.html")


@pytest.fixture
def knowledge_panel_html():
    return load_fixture("knowledge_panel.html")


@pytest.fixture
def local_pack_html():
    return load_fixture("local_pack.html")


@pytest.fixture
def ads_html():
    return load_fixture("ads_top.html")


@pytest.fixture
def video_html():
    return load_fixture("video_carousel.html")


@pytest.fixture
def empty_html():
    return load_fixture("empty_results.html")
