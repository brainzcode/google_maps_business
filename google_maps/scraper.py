"""Core async scraping engine for Google Maps business listings."""

from __future__ import annotations

import logging
import sys

from playwright.async_api import Page, Locator
from playwright.async_api import TimeoutError as PwTimeout

from google_maps.config import ScraperConfig
from google_maps.models import Business, BusinessList
from google_maps.retry import retry, RetryExhausted
from google_maps.utils import (
    coords_from_url,
    human_delay,
    parse_rating,
    parse_review_count,
    parse_price_level,
)

logger = logging.getLogger(__name__)

# ── Selectors (with fallbacks) ──────────────────────────────────────────────

LISTING = 'a[href*="https://www.google.com/maps/place"]'
FEED = 'div[role="feed"]'
SEARCHBOX = 'input[name="q"]'
END_TEXT = "You've reached the end of the list"

# Each field has a primary selector and optional fallbacks
FIELD_SELECTORS: dict[str, list[str]] = {
    "address": [
        'button[data-item-id="address"] div.fontBodyMedium',
        '[data-item-id="address"]',
    ],
    "website_text": [
        'a[data-item-id="authority"] div.fontBodyMedium',
        '[data-item-id="authority"]',
    ],
    "phone_text": [
        'button[data-item-id^="phone:tel:"] div.fontBodyMedium',
        '[data-item-id^="phone:tel:"]',
    ],
    "plus_code": [
        'button[data-item-id="oloc"] div.fontBodyMedium',
        '[data-item-id="oloc"]',
    ],
}

NAME_SELECTORS = ["h1", "h2.fontHeadlineLarge"]
# Headings to skip — exact matches and prefixes
_IGNORED_NAMES_EXACT = {"Results", "Google Maps"}
_IGNORED_NAMES_PREFIX = ("Sponsored",)
CATEGORY_SELECTORS = [
    'button[jsaction*="pane.rating.category"]',
    'button[jsaction*="category"]',
]
RATING_SELECTORS = [
    'div[jsaction*="pane.reviewChart.moreReviews"] div[role="img"]',
    'div[role="img"][aria-label*="star"]',
    'span[role="img"][aria-label*="star"]',
]
REVIEW_SELECTORS = [
    'button[jsaction*="pane.reviewChart.moreReviews"]',
    'span[aria-label*="review"]',
]
HOURS_SELECTORS = ['[data-item-id="oh"]']
SERVICE_SELECTORS = ['div[aria-label*="Service options"]']

# Phrases Google shows when it thinks the client is a bot or the IP is
# rate-limited. Case-insensitive substring match against the page HTML.
_BLOCK_MARKERS = (
    "unusual traffic from your computer",
    "our systems have detected unusual traffic",
    "to continue, please type the characters",
    "/sorry/index",
    "recaptcha",
)


class BlockDetected(Exception):
    """Raised when Google serves a captcha or 'unusual traffic' page."""


# ── Low-level page helpers ──────────────────────────────────────────────────

async def _text(page: Page, selectors: list[str], timeout: int = 2000) -> str:
    """Return inner text from the first matching selector, or empty string."""
    for sel in selectors:
        try:
            loc = page.locator(sel)
            if await loc.count() > 0:
                text = await loc.first.inner_text(timeout=timeout)
                if text and text.strip():
                    return text.strip()
        except Exception:
            continue
    return ""


async def _attr(page: Page, selectors: list[str], attr: str, timeout: int = 2000) -> str:
    """Return attribute value from the first matching selector, or empty string."""
    for sel in selectors:
        try:
            loc = page.locator(sel)
            if await loc.count() > 0:
                val = await loc.first.get_attribute(attr, timeout=timeout)
                if val and val.strip():
                    return val.strip()
        except Exception:
            continue
    return ""


async def detect_block(page: Page) -> bool:
    """Return True if the current page looks like a Google block / captcha."""
    try:
        url = (page.url or "").lower()
        for marker in _BLOCK_MARKERS:
            if marker in url:
                return True
        # Fast substring check on HTML
        html = (await page.content()).lower()
    except Exception:
        return False
    return any(marker in html for marker in _BLOCK_MARKERS)


# ── Extraction ──────────────────────────────────────────────────────────────

async def extract_business(page: Page, config: ScraperConfig) -> Business:
    """Pull every available field from the open business detail panel."""
    b = Business()

    # Name — skip generic headings like "Results" and "Sponsored ..."
    for sel in NAME_SELECTORS:
        try:
            els = await page.locator(sel).all()
            for el in els:
                raw = (await el.inner_text(timeout=2000)).strip()
                # Take only the first line (Google sometimes appends icons/child text)
                text = raw.split("\n")[0].strip()
                if not text:
                    continue
                if text in _IGNORED_NAMES_EXACT:
                    continue
                if text.startswith(_IGNORED_NAMES_PREFIX):
                    continue
                b.name = text
                break
        except Exception:
            continue
        if b.name:
            break

    # Category
    b.category = await _text(page, CATEGORY_SELECTORS)

    # Rating
    label = await _attr(page, RATING_SELECTORS, "aria-label")
    if label:
        b.rating = parse_rating(label)

    # Review count
    for sel in REVIEW_SELECTORS:
        raw = await _text(page, [sel]) or await _attr(page, [sel], "aria-label")
        if raw:
            b.reviews = parse_review_count(raw)
            if b.reviews is not None:
                break

    # Price level
    price_label = await _attr(page, ['span[aria-label*="Price"]'], "aria-label")
    if price_label:
        b.price_level = parse_price_level(price_label)

    # Address
    b.address = await _text(page, FIELD_SELECTORS["address"])

    # Plus code
    b.plus_code = await _text(page, FIELD_SELECTORS["plus_code"])

    # Website — prefer the actual href over truncated display text
    href = await _attr(page, ['a[data-item-id="authority"]'], "href")
    if href and not href.startswith("https://www.google"):
        b.website = href
    else:
        b.website = await _text(page, FIELD_SELECTORS["website_text"])

    # Phone — prefer clean number from data attribute
    phone_attr = await _attr(page, ['button[data-item-id^="phone:tel:"]'], "data-item-id")
    if phone_attr:
        b.phone = phone_attr.replace("phone:tel:", "")
    else:
        b.phone = await _text(page, FIELD_SELECTORS["phone_text"])

    # Email — check data-item-id and mailto links
    email_attr = await _attr(page, ['[data-item-id^="email"]'], "data-item-id")
    if email_attr:
        b.email = email_attr.replace("email:", "").replace("mailto:", "")
    else:
        mailto_href = await _attr(page, ['a[href^="mailto:"]'], "href")
        if mailto_href:
            b.email = mailto_href.replace("mailto:", "").split("?")[0]

    # Hours
    h = await _attr(page, HOURS_SELECTORS, "aria-label")
    b.hours = h if h else await _text(page, HOURS_SELECTORS)

    # Status
    for status_text in ["Temporarily closed", "Permanently closed"]:
        try:
            loc = page.locator(f'span:has-text("{status_text}")')
            if await loc.count() > 0:
                b.status = status_text
                break
        except Exception:
            continue
    else:
        hours_span = await _text(page, ['[data-item-id="oh"] span'])
        if "Closed" in hours_span or "Open" in hours_span:
            b.status = hours_span

    # Service options
    svc = await _attr(page, SERVICE_SELECTORS, "aria-label")
    if svc:
        b.service_options = svc.replace("Service options: ", "")

    # Coordinates and URL
    b.url = page.url
    b.latitude, b.longitude = coords_from_url(page.url)

    return b


# ── Scrolling ───────────────────────────────────────────────────────────────

async def scroll_listings(page: Page, target: int, config: ScraperConfig) -> list[Locator]:
    """Scroll the results feed until we have enough listings or hit the end."""
    prev_count = 0
    stale_cycles = 0

    while True:
        # Hover over feed to ensure scroll targets it
        feed = page.locator(FEED)
        if await feed.count() > 0:
            try:
                await feed.hover()
            except Exception:
                pass

        await page.mouse.wheel(0, 5000)

        # Human-like wait between scrolls
        delay = human_delay(config.scroll_delay_min, config.scroll_delay_max)
        await page.wait_for_timeout(delay)

        current_count = await page.locator(LISTING).count()

        if current_count >= target:
            logger.info("Target reached: %d listings", current_count)
            break

        end_marker = page.get_by_text(END_TEXT)
        if await end_marker.count() > 0:
            logger.info("End of results: %d listings", current_count)
            break

        if current_count == prev_count:
            stale_cycles += 1
            if stale_cycles >= config.scroll_stale_limit:
                logger.info("Stopped (no new results after %d cycles): %d listings", stale_cycles, current_count)
                break
        else:
            stale_cycles = 0

        prev_count = current_count
        sys.stdout.write(f"\r  Scrolling... {current_count} listings")
        sys.stdout.flush()

    print()  # newline after progress
    links = await page.locator(LISTING).all()

    # Filter out sponsored listings — they have a "Sponsored" span inside the parent
    organic: list[Locator] = []
    for link in links:
        parent = link.locator("xpath=..")
        try:
            is_sponsored = await parent.locator('span:has-text("Sponsored")').count() > 0
        except Exception:
            is_sponsored = False
        if not is_sponsored:
            organic.append(parent)
        if len(organic) >= target:
            break

    if len(organic) < len(links):
        logger.info("Filtered %d sponsored listings", len(links) - len(organic))

    return organic


# ── Single listing extraction with retry ────────────────────────────────────

async def _extract_one(
    page: Page,
    listing: Locator,
    index: int,
    total: int,
    config: ScraperConfig,
) -> Business | None:
    """Click a listing, wait for detail panel, and extract. Returns None on failure."""

    @retry(
        max_attempts=config.max_retries,
        base_delay=config.retry_base_delay,
        max_delay=config.retry_max_delay,
        retryable=(Exception,),
    )
    async def _click_and_extract() -> Business:
        await listing.click()
        try:
            await page.wait_for_selector("h1", state="attached", timeout=8000)
        except PwTimeout:
            pass
        # Human-like delay after clicking
        delay = human_delay(config.min_action_delay, config.max_action_delay)
        await page.wait_for_timeout(delay)
        if await detect_block(page):
            raise BlockDetected("Google served a captcha / unusual-traffic page")
        return await extract_business(page, config)

    try:
        b = await _click_and_extract()
        return b
    except RetryExhausted as e:
        logger.error("[%d/%d] Gave up after %d retries: %s", index, total, config.max_retries, e.last_error)
        if isinstance(e.last_error, BlockDetected):
            raise e.last_error
        return None


# ── Scrape one query ────────────────────────────────────────────────────────

async def scrape_query(page: Page, query: str, config: ScraperConfig) -> BusinessList:
    """Execute one search query and return all extracted businesses.

    Raises :class:`BlockDetected` if Google serves a captcha — the caller can
    then rotate proxies and retry.
    """
    results = BusinessList()

    # Type the query with a human-like delay
    box = page.locator(SEARCHBOX)
    await box.click()
    await box.fill(query)
    await page.wait_for_timeout(human_delay(200, 500))
    await page.keyboard.press("Enter")

    # Wait for listings to appear — try the feed/listing selector first,
    # fall back to h1 for single-result pages
    try:
        await page.wait_for_selector(LISTING, timeout=15000)
    except PwTimeout:
        # Maybe a single-result page (no feed, just a detail panel)
        try:
            await page.wait_for_selector("h1", timeout=5000)
        except PwTimeout:
            if await detect_block(page):
                raise BlockDetected(f"blocked while searching '{query}'")
            logger.warning("No results found for '%s'", query)
            return results

    await page.wait_for_timeout(config.page_load_wait)

    if await detect_block(page):
        raise BlockDetected(f"blocked after search '{query}'")

    # Single result — Google went straight to the detail panel
    if await page.locator(FEED).count() == 0 and await page.locator(LISTING).count() == 0:
        if await page.locator("h1").count() > 0:
            logger.info("Single result detected")
            b = await extract_business(page, config)
            results.add(b)
            return results

    # Multiple results — scroll then extract each
    listings = await scroll_listings(page, config.max_results, config)
    total = len(listings)

    for i, listing in enumerate(listings):
        b = await _extract_one(page, listing, i + 1, total, config)
        if b is None:
            print(f"  [{i + 1}/{total}] error: extraction failed")
            continue

        if b.is_valid:
            added = results.add(b)
            tag = "+" if added else "skip (dup)"
            print(f"  [{i + 1}/{total}] {tag}: {b.name}")
        else:
            print(f"  [{i + 1}/{total}] skip: no name found")

    return results
