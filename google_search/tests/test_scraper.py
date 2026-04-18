"""Tests for SERP extraction logic using Playwright with HTML fixtures.

Runs extraction functions against real Playwright pages loaded with fixture HTML.
Uses a single browser instance shared across all tests via module-level setup.
"""

import asyncio

import pytest
from playwright.async_api import async_playwright

from google_search.config import SerpConfig
from google_search.scraper import (
    _extract_ads,
    _extract_featured_snippet,
    _extract_knowledge_panel,
    _extract_local_pack,
    _extract_organic,
    _extract_people_also_ask,
    _extract_related_searches,
    _extract_result_stats,
    _extract_videos,
    check_captcha,
    extract_serp_page,
)
from google_search.tests.conftest import load_fixture


def _make_loop():
    """Create a fresh event loop for async test execution."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


async def _run_extraction_tests():
    """Run all extraction tests within a single browser session.

    Returns a dict of test_name -> (passed: bool, error: str).
    """
    results = {}

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()

    async def run_test(name, coro):
        try:
            await coro
            results[name] = (True, "")
        except AssertionError as e:
            results[name] = (False, str(e))
        except Exception as e:
            results[name] = (False, f"{type(e).__name__}: {e}")

    # ── Organic results ───────────────────────────────────────────

    await page.set_content(load_fixture("organic_results.html"))
    organic = await _extract_organic(page)

    async def test_organic_count():
        assert len(organic) == 5

    async def test_organic_first():
        assert organic[0].title == "First Result Title"
        assert organic[0].url == "https://example.com/first-result"
        assert organic[0].position == 1

    async def test_organic_displayed_url():
        assert organic[0].displayed_url == "example.com"

    async def test_organic_description():
        assert "first result" in organic[0].description.lower()

    async def test_organic_sitelinks():
        third = organic[2]
        assert len(third.sitelinks) == 2
        assert third.sitelinks[0]["title"] == "Subpage One"
        assert third.sitelinks[0]["url"] == "https://example.net/third-result/page1"

    async def test_organic_positions():
        for i, r in enumerate(organic):
            assert r.position == i + 1, f"Position {r.position} != {i + 1}"

    await run_test("organic_count", test_organic_count())
    await run_test("organic_first", test_organic_first())
    await run_test("organic_displayed_url", test_organic_displayed_url())
    await run_test("organic_description", test_organic_description())
    await run_test("organic_sitelinks", test_organic_sitelinks())
    await run_test("organic_positions", test_organic_positions())

    # Empty results
    await page.set_content(load_fixture("empty_results.html"))
    empty_organic = await _extract_organic(page)

    async def test_organic_empty():
        assert len(empty_organic) == 0

    await run_test("organic_empty", test_organic_empty())

    # ── Featured snippet ──────────────────────────────────────────

    await page.set_content(load_fixture("featured_snippet.html"))
    snippet = await _extract_featured_snippet(page)

    async def test_snippet_paragraph():
        assert snippet is not None
        assert "Python" in snippet.content
        assert snippet.content_type == "paragraph"
        assert snippet.title == "About Python - Python.org"
        assert snippet.url == "https://python.org/about"

    await run_test("snippet_paragraph", test_snippet_paragraph())

    await page.set_content(load_fixture("featured_snippet_list.html"))
    list_snippet = await _extract_featured_snippet(page)

    async def test_snippet_list():
        assert list_snippet is not None
        assert list_snippet.content_type == "list"
        assert "Django" in list_snippet.content
        assert "Flask" in list_snippet.content

    await run_test("snippet_list", test_snippet_list())

    await page.set_content(load_fixture("organic_results.html"))
    no_snippet = await _extract_featured_snippet(page)

    async def test_no_snippet():
        assert no_snippet is None

    await run_test("no_snippet", test_no_snippet())

    # ── People Also Ask ───────────────────────────────────────────

    await page.set_content(load_fixture("people_also_ask.html"))
    paa = await _extract_people_also_ask(page)

    async def test_paa_questions():
        assert len(paa) == 4
        assert paa[0].question == "What is Python used for?"
        assert paa[1].question == "Is Python easy to learn?"

    await run_test("paa_questions", test_paa_questions())

    await page.set_content(load_fixture("organic_results.html"))
    no_paa = await _extract_people_also_ask(page)

    async def test_no_paa():
        assert len(no_paa) == 0

    await run_test("no_paa", test_no_paa())

    # ── Knowledge Panel ───────────────────────────────────────────

    await page.set_content(load_fixture("knowledge_panel.html"))
    kp = await _extract_knowledge_panel(page)

    async def test_kp():
        assert kp is not None
        assert kp.title == "Python"
        assert kp.subtitle == "Programming Language"
        assert "interpreted" in kp.description.lower()

    async def test_kp_attributes():
        assert kp is not None
        assert len(kp.attributes) >= 2

    await run_test("kp", test_kp())
    await run_test("kp_attributes", test_kp_attributes())

    await page.set_content(load_fixture("organic_results.html"))
    no_kp = await _extract_knowledge_panel(page)

    async def test_no_kp():
        assert no_kp is None

    await run_test("no_kp", test_no_kp())

    # ── Ads ───────────────────────────────────────────────────────

    await page.set_content(load_fixture("ads_top.html"))
    ads = await _extract_ads(page)

    async def test_top_ads():
        top = [a for a in ads if a.is_top]
        assert len(top) == 2
        assert top[0].title == "Ad Title One - Best Service"
        assert top[0].url == "https://advert1.com/landing"

    async def test_bottom_ads():
        bottom = [a for a in ads if not a.is_top]
        assert len(bottom) == 1
        assert bottom[0].title == "Bottom Ad Title"

    await run_test("top_ads", test_top_ads())
    await run_test("bottom_ads", test_bottom_ads())

    await page.set_content(load_fixture("organic_results.html"))
    no_ads = await _extract_ads(page)

    async def test_no_ads():
        assert len(no_ads) == 0

    await run_test("no_ads", test_no_ads())

    # ── Local Pack ────────────────────────────────────────────────

    await page.set_content(load_fixture("local_pack.html"))
    local = await _extract_local_pack(page)

    async def test_local_pack():
        assert len(local) == 3
        assert local[0].name == "Joe's Plumbing"
        assert local[0].rating == 4.8
        assert local[0].reviews == 234

    async def test_local_address():
        assert "Chicago" in local[0].address

    await run_test("local_pack", test_local_pack())
    await run_test("local_address", test_local_address())

    await page.set_content(load_fixture("organic_results.html"))
    no_local = await _extract_local_pack(page)

    async def test_no_local():
        assert len(no_local) == 0

    await run_test("no_local", test_no_local())

    # ── Videos ────────────────────────────────────────────────────

    await page.set_content(load_fixture("video_carousel.html"))
    videos = await _extract_videos(page)

    async def test_videos():
        assert len(videos) == 3
        assert videos[0].title == "How to Learn Python in 2025"
        assert videos[0].source == "YouTube"
        assert videos[0].duration == "15:32"

    async def test_video_urls():
        assert "youtube.com" in videos[0].url
        assert "vimeo.com" in videos[2].url

    await run_test("videos", test_videos())
    await run_test("video_urls", test_video_urls())

    await page.set_content(load_fixture("organic_results.html"))
    no_videos = await _extract_videos(page)

    async def test_no_videos():
        assert len(no_videos) == 0

    await run_test("no_videos", test_no_videos())

    # ── Related Searches ──────────────────────────────────────────

    await page.set_content(load_fixture("organic_results.html"))
    related = await _extract_related_searches(page)

    async def test_related():
        assert len(related) == 3
        assert related[0].query == "related query one"

    await run_test("related", test_related())

    await page.set_content(load_fixture("empty_results.html"))
    no_related = await _extract_related_searches(page)

    async def test_no_related():
        assert len(no_related) == 0

    await run_test("no_related", test_no_related())

    # ── Result Stats ──────────────────────────────────────────────

    await page.set_content(load_fixture("organic_results.html"))
    total, search_time = await _extract_result_stats(page)

    async def test_result_stats():
        assert "1,234,000" in total
        assert "0.52" in search_time

    await run_test("result_stats", test_result_stats())

    await page.set_content(load_fixture("empty_results.html"))
    no_total, no_time = await _extract_result_stats(page)

    async def test_no_stats():
        assert no_total == ""
        assert no_time == ""

    await run_test("no_stats", test_no_stats())

    # ── CAPTCHA Detection ─────────────────────────────────────────

    await page.set_content(load_fixture("organic_results.html"))
    captcha_false = await check_captcha(page)

    async def test_no_captcha():
        assert captcha_false is False

    await run_test("no_captcha", test_no_captcha())

    await page.set_content('<html><body><form id="captcha-form"><div>Prove you are human</div></form></body></html>')
    captcha_true = await check_captcha(page)

    async def test_captcha_detected():
        assert captcha_true is True

    await run_test("captcha_detected", test_captcha_detected())

    # ── Full SERP Page Extraction ─────────────────────────────────

    await page.set_content(load_fixture("organic_results.html"))
    config = SerpConfig()
    serp = await extract_serp_page(page, "test query", 0, config)

    async def test_full_extraction():
        assert serp.query == "test query"
        assert serp.page_number == 0
        assert len(serp.organic) == 5
        assert len(serp.related_searches) == 3

    await run_test("full_extraction", test_full_extraction())

    await page.set_content(load_fixture("organic_results.html"))
    organic_only_config = SerpConfig(
        extract_ads=False,
        extract_featured_snippet=False,
        extract_people_also_ask=False,
        extract_knowledge_panel=False,
        extract_local_pack=False,
        extract_videos=False,
        extract_related_searches=False,
    )
    serp_organic = await extract_serp_page(page, "test", 0, organic_only_config)

    async def test_organic_only():
        assert len(serp_organic.organic) == 5
        assert len(serp_organic.ads) == 0
        assert serp_organic.featured_snippet is None
        assert len(serp_organic.people_also_ask) == 0

    await run_test("organic_only", test_organic_only())

    # Cleanup
    await browser.close()
    await pw.stop()

    return results


# ── pytest parametrized tests ─────────────────────────────────────────────
# Run all extraction tests once in a single browser session, then
# report each as an individual pytest test case.

_test_results = None


def _get_results():
    global _test_results
    if _test_results is None:
        loop = _make_loop()
        try:
            _test_results = loop.run_until_complete(_run_extraction_tests())
        finally:
            loop.close()
    return _test_results


# Discover test names at import time so pytest can parametrize
_ALL_TESTS = [
    "organic_count", "organic_first", "organic_displayed_url",
    "organic_description", "organic_sitelinks", "organic_positions",
    "organic_empty",
    "snippet_paragraph", "snippet_list", "no_snippet",
    "paa_questions", "no_paa",
    "kp", "kp_attributes", "no_kp",
    "top_ads", "bottom_ads", "no_ads",
    "local_pack", "local_address", "no_local",
    "videos", "video_urls", "no_videos",
    "related", "no_related",
    "result_stats", "no_stats",
    "no_captcha", "captcha_detected",
    "full_extraction", "organic_only",
]


@pytest.mark.parametrize("test_name", _ALL_TESTS)
def test_extraction(test_name):
    """Run a single extraction test (backed by shared browser session)."""
    results = _get_results()
    assert test_name in results, f"Test '{test_name}' was not executed"
    passed, error = results[test_name]
    if not passed:
        pytest.fail(error)
