"""Tests for SERP data models."""

import pytest

from google_search.models import (
    AdResult,
    FeaturedSnippet,
    KnowledgePanelItem,
    LocalPackResult,
    OrganicResult,
    PeopleAlsoAskItem,
    RelatedSearch,
    SerpPage,
    SerpResultSet,
    VideoResult,
)


class TestOrganicResult:
    def test_is_valid_with_title_and_url(self):
        r = OrganicResult(title="Test", url="https://example.com")
        assert r.is_valid is True

    def test_is_invalid_without_title(self):
        r = OrganicResult(url="https://example.com")
        assert r.is_valid is False

    def test_is_invalid_without_url(self):
        r = OrganicResult(title="Test")
        assert r.is_valid is False

    def test_dedup_key_strips_query_and_trailing_slash(self):
        r = OrganicResult(url="https://example.com/page?ref=123")
        assert r.dedup_key == "https://example.com/page"

    def test_to_dict(self):
        r = OrganicResult(position=1, title="Test", url="https://example.com")
        d = r.to_dict()
        assert d["position"] == 1
        assert d["title"] == "Test"
        assert d["url"] == "https://example.com"
        assert "sitelinks" in d


class TestAdResult:
    def test_is_valid(self):
        ad = AdResult(title="Ad Title")
        assert ad.is_valid is True

    def test_is_invalid_empty(self):
        ad = AdResult()
        assert ad.is_valid is False

    def test_default_is_top(self):
        ad = AdResult(title="Ad")
        assert ad.is_top is True


class TestFeaturedSnippet:
    def test_is_valid(self):
        s = FeaturedSnippet(content="Some answer text")
        assert s.is_valid is True

    def test_is_invalid_empty(self):
        s = FeaturedSnippet()
        assert s.is_valid is False

    def test_default_content_type(self):
        s = FeaturedSnippet(content="text")
        assert s.content_type == "paragraph"


class TestPeopleAlsoAskItem:
    def test_is_valid(self):
        p = PeopleAlsoAskItem(question="What is Python?")
        assert p.is_valid is True

    def test_is_invalid_empty(self):
        p = PeopleAlsoAskItem()
        assert p.is_valid is False


class TestKnowledgePanelItem:
    def test_is_valid(self):
        kp = KnowledgePanelItem(title="Python")
        assert kp.is_valid is True

    def test_attributes_dict(self):
        kp = KnowledgePanelItem(title="Python", attributes={"creator": "Guido"})
        d = kp.to_dict()
        assert d["attributes"] == {"creator": "Guido"}


class TestLocalPackResult:
    def test_is_valid(self):
        lp = LocalPackResult(name="Joe's Plumbing")
        assert lp.is_valid is True

    def test_optional_fields(self):
        lp = LocalPackResult(name="Shop", rating=4.5, reviews=100)
        d = lp.to_dict()
        assert d["rating"] == 4.5
        assert d["reviews"] == 100


class TestVideoResult:
    def test_is_valid(self):
        v = VideoResult(title="Video Title", url="https://youtube.com/watch?v=123")
        assert v.is_valid is True

    def test_is_invalid_no_url(self):
        v = VideoResult(title="Title")
        assert v.is_valid is False


class TestRelatedSearch:
    def test_is_valid(self):
        rs = RelatedSearch(query="related query")
        assert rs.is_valid is True

    def test_is_invalid_empty(self):
        rs = RelatedSearch()
        assert rs.is_valid is False


class TestSerpPage:
    def test_to_dict(self):
        page = SerpPage(
            query="test",
            page_number=0,
            organic=[OrganicResult(position=1, title="Test", url="https://example.com")],
            related_searches=[RelatedSearch(query="related")],
        )
        d = page.to_dict()
        assert d["query"] == "test"
        assert len(d["organic"]) == 1
        assert len(d["related_searches"]) == 1
        assert d["featured_snippet"] is None
        assert d["knowledge_panel"] is None


class TestSerpResultSet:
    def test_add_page(self):
        rs = SerpResultSet()
        page = SerpPage(
            query="test",
            organic=[OrganicResult(position=1, title="Test", url="https://example.com")],
        )
        rs.add_page(page)
        assert len(rs) == 1

    def test_dedup_across_pages(self):
        rs = SerpResultSet()
        page1 = SerpPage(
            query="test",
            organic=[
                OrganicResult(position=1, title="Test", url="https://example.com/page"),
                OrganicResult(position=2, title="Test 2", url="https://other.com/page"),
            ],
        )
        page2 = SerpPage(
            query="test",
            page_number=1,
            organic=[
                OrganicResult(position=1, title="Test Dupe", url="https://example.com/page"),
                OrganicResult(position=2, title="Test 3", url="https://new.com/page"),
            ],
        )
        rs.add_page(page1)
        rs.add_page(page2)
        assert len(rs) == 3  # 2 from page1 + 1 new from page2

    def test_all_organic(self):
        rs = SerpResultSet()
        page = SerpPage(
            query="test",
            organic=[
                OrganicResult(position=1, title="A", url="https://a.com"),
                OrganicResult(position=2, title="B", url="https://b.com"),
            ],
        )
        rs.add_page(page)
        assert len(rs.all_organic()) == 2

    def test_all_urls(self):
        rs = SerpResultSet()
        page = SerpPage(
            query="test",
            organic=[
                OrganicResult(position=1, title="A", url="https://a.com"),
                OrganicResult(position=2, title="B", url="https://b.com"),
            ],
        )
        rs.add_page(page)
        assert rs.all_urls() == ["https://a.com", "https://b.com"]

    def test_bool_empty(self):
        rs = SerpResultSet()
        assert not rs

    def test_bool_with_results(self):
        rs = SerpResultSet()
        page = SerpPage(
            query="test",
            organic=[OrganicResult(position=1, title="A", url="https://a.com")],
        )
        rs.add_page(page)
        assert rs
