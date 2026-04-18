"""Tests for pure-Python pieces of google_maps.scraper.

The async page-interaction code is covered by smoke-testing against a live
Maps page (see README). Here we lock down the constants, selectors and the
block-detection heuristic that are unit-testable without a browser.
"""

from __future__ import annotations

import pytest

from google_maps import scraper
from google_maps.scraper import (
    BlockDetected,
    CATEGORY_SELECTORS,
    END_TEXT,
    FEED,
    FIELD_SELECTORS,
    HOURS_SELECTORS,
    LISTING,
    NAME_SELECTORS,
    RATING_SELECTORS,
    REVIEW_SELECTORS,
    SEARCHBOX,
    SERVICE_SELECTORS,
    _BLOCK_MARKERS,
    detect_block,
)


class TestSelectors:
    def test_listing_targets_place_links(self):
        assert "/maps/place" in LISTING
        assert LISTING.startswith("a[")

    def test_feed_role(self):
        assert 'role="feed"' in FEED

    def test_searchbox_name_attr(self):
        assert 'name="q"' in SEARCHBOX

    def test_end_text_not_empty(self):
        assert END_TEXT
        assert "end" in END_TEXT.lower()

    def test_field_selectors_have_fallbacks(self):
        for field, sels in FIELD_SELECTORS.items():
            assert len(sels) >= 1, f"{field} has no selectors"

    def test_selector_lists_non_empty(self):
        for lst in (
            NAME_SELECTORS,
            CATEGORY_SELECTORS,
            RATING_SELECTORS,
            REVIEW_SELECTORS,
            HOURS_SELECTORS,
            SERVICE_SELECTORS,
        ):
            assert isinstance(lst, list) and lst


class TestBlockDetected:
    def test_is_exception(self):
        assert issubclass(BlockDetected, Exception)

    def test_message_passthrough(self):
        err = BlockDetected("captcha served")
        assert "captcha" in str(err)


class TestBlockMarkers:
    def test_known_markers_present(self):
        assert any("unusual traffic" in m for m in _BLOCK_MARKERS)
        assert any("recaptcha" in m for m in _BLOCK_MARKERS)
        assert any("/sorry/" in m for m in _BLOCK_MARKERS)

    def test_markers_lowercase(self):
        for m in _BLOCK_MARKERS:
            assert m == m.lower()


class _FakePage:
    """Minimal Page stand-in for testing detect_block without a browser."""

    def __init__(self, url: str = "https://maps.google.com", html: str = ""):
        self.url = url
        self._html = html

    async def content(self) -> str:
        return self._html


class TestDetectBlock:
    @pytest.mark.asyncio
    async def test_clean_page_is_not_blocked(self):
        page = _FakePage(html="<html><body>Google Maps</body></html>")
        assert await detect_block(page) is False

    @pytest.mark.asyncio
    async def test_url_sorry_triggers(self):
        page = _FakePage(url="https://www.google.com/sorry/index?continue=...")
        assert await detect_block(page) is True

    @pytest.mark.asyncio
    async def test_recaptcha_in_body_triggers(self):
        page = _FakePage(html='<html><body><div class="g-recaptcha"></div></body></html>')
        assert await detect_block(page) is True

    @pytest.mark.asyncio
    async def test_unusual_traffic_phrase_triggers(self):
        page = _FakePage(
            html="<html>Our systems have detected unusual traffic from your computer network.</html>"
        )
        assert await detect_block(page) is True

    @pytest.mark.asyncio
    async def test_content_failure_is_not_block(self):
        class BrokenPage:
            url = "https://maps.google.com"

            async def content(self):
                raise RuntimeError("disconnected")

        assert await detect_block(BrokenPage()) is False
