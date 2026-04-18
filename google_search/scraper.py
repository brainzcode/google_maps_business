"""Core async extraction engine for Google SERP data."""

import logging
import re
import sys

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PwTimeout

from google_maps.retry import retry, RetryExhausted

from google_search.config import SerpConfig
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
from google_search.selectors import (
    AD_BOTTOM_CONTAINER,
    AD_DESCRIPTION,
    AD_DISPLAYED_URL,
    AD_LINK,
    AD_TITLE,
    AD_TOP_CONTAINER,
    CAPTCHA_INDICATORS,
    CONSENT_BUTTON_TEXTS,
    KP_ATTRIBUTES,
    KP_CONTAINER,
    KP_DESCRIPTION,
    KP_SUBTITLE,
    KP_TITLE,
    LOCAL_ADDRESS,
    LOCAL_CATEGORY,
    LOCAL_CONTAINER,
    LOCAL_NAME,
    LOCAL_RATING,
    LOCAL_REVIEWS,
    ORGANIC_CONTAINER,
    ORGANIC_DATE,
    ORGANIC_DESCRIPTION,
    ORGANIC_DISPLAYED_URL,
    ORGANIC_LINK,
    ORGANIC_SITELINKS,
    ORGANIC_TITLE,
    PAA_CONTAINER,
    PAA_QUESTION,
    RELATED_CONTAINER,
    RELATED_QUERY,
    RESULT_STATS,
    SNIPPET_CONTAINER,
    SNIPPET_CONTENT,
    SNIPPET_LINK,
    SNIPPET_LIST_ITEMS,
    SNIPPET_TITLE,
    VIDEO_CONTAINER,
    VIDEO_DATE,
    VIDEO_DURATION,
    VIDEO_LINK,
    VIDEO_SOURCE,
    VIDEO_TITLE,
)
from google_search.utils import clean_url, human_delay, parse_result_count, parse_search_time

logger = logging.getLogger(__name__)


# ── Low-level page helpers ─────────────────────────────────────────────────


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


async def _text_within(parent, selectors: list[str], timeout: int = 2000) -> str:
    """Return inner text from the first matching selector within a parent locator."""
    for sel in selectors:
        try:
            loc = parent.locator(sel)
            if await loc.count() > 0:
                text = await loc.first.inner_text(timeout=timeout)
                if text and text.strip():
                    return text.strip()
        except Exception:
            continue
    return ""


async def _attr_within(parent, selectors: list[str], attr: str, timeout: int = 2000) -> str:
    """Return attribute from the first matching selector within a parent locator."""
    for sel in selectors:
        try:
            loc = parent.locator(sel)
            if await loc.count() > 0:
                val = await loc.first.get_attribute(attr, timeout=timeout)
                if val and val.strip():
                    return val.strip()
        except Exception:
            continue
    return ""


# ── CAPTCHA and consent ────────────────────────────────────────────────────


async def check_captcha(page: Page) -> bool:
    """Check if Google is showing a CAPTCHA. Returns True if detected."""
    for sel in CAPTCHA_INDICATORS:
        try:
            if await page.locator(sel).count() > 0:
                return True
        except Exception:
            continue
    return False


async def dismiss_consent(page: Page) -> None:
    """Dismiss Google cookie/consent dialogs if present."""
    for btn_text in CONSENT_BUTTON_TEXTS:
        try:
            await page.click(f'button:has-text("{btn_text}")', timeout=2000)
            return
        except PwTimeout:
            continue


# ── Feature extractors ─────────────────────────────────────────────────────


async def _extract_organic(page: Page) -> list[OrganicResult]:
    """Extract organic search results."""
    results = []

    for container_sel in ORGANIC_CONTAINER:
        containers = page.locator(container_sel)
        count = await containers.count()
        if count > 0:
            for i in range(count):
                try:
                    item = containers.nth(i)
                    title = await _text_within(item, ORGANIC_TITLE)
                    if not title:
                        continue

                    href = await _attr_within(item, ORGANIC_LINK, "href")
                    url = clean_url(href)
                    if not url or url.startswith("#") or url.startswith("/"):
                        continue

                    displayed_url = await _text_within(item, ORGANIC_DISPLAYED_URL)
                    description = await _text_within(item, ORGANIC_DESCRIPTION)
                    date = await _text_within(item, ORGANIC_DATE)

                    sitelinks = []
                    for sl_sel in ORGANIC_SITELINKS:
                        sl_links = item.locator(sl_sel)
                        sl_count = await sl_links.count()
                        for j in range(sl_count):
                            sl_item = sl_links.nth(j)
                            sl_text = ""
                            sl_href = ""
                            try:
                                sl_text = (await sl_item.inner_text(timeout=1000)).strip()
                                sl_href = clean_url(await sl_item.get_attribute("href", timeout=1000) or "")
                            except Exception:
                                pass
                            if sl_text and sl_href:
                                sitelinks.append({"title": sl_text, "url": sl_href})
                        if sitelinks:
                            break

                    result = OrganicResult(
                        position=len(results) + 1,
                        title=title,
                        url=url,
                        displayed_url=displayed_url,
                        description=description,
                        date=date,
                        sitelinks=sitelinks,
                    )
                    if result.is_valid:
                        results.append(result)
                except Exception as e:
                    logger.debug("Failed to extract organic result %d: %s", i, e)
                    continue
            if results:
                break

    return results


async def _extract_featured_snippet(page: Page) -> FeaturedSnippet | None:
    """Extract featured snippet / answer box if present."""
    for container_sel in SNIPPET_CONTAINER:
        try:
            container = page.locator(container_sel)
            if await container.count() == 0:
                continue

            content = await _text_within(container, SNIPPET_CONTENT)
            content_type = "paragraph"

            if not content:
                items = []
                for li_sel in SNIPPET_LIST_ITEMS:
                    li_elements = page.locator(li_sel)
                    li_count = await li_elements.count()
                    for i in range(li_count):
                        try:
                            text = (await li_elements.nth(i).inner_text(timeout=1000)).strip()
                            if text:
                                items.append(text)
                        except Exception:
                            continue
                    if items:
                        break

                if items:
                    content = "\n".join(items)
                    content_type = "list"

            if not content:
                continue

            title = await _text_within(container, SNIPPET_TITLE)
            href = await _attr_within(container, SNIPPET_LINK, "href")
            url = clean_url(href)

            snippet = FeaturedSnippet(
                title=title,
                url=url,
                content=content,
                content_type=content_type,
            )
            if snippet.is_valid:
                return snippet
        except Exception as e:
            logger.debug("Failed to extract featured snippet: %s", e)
            continue

    return None


async def _extract_people_also_ask(page: Page) -> list[PeopleAlsoAskItem]:
    """Extract People Also Ask questions."""
    items = []

    for container_sel in PAA_CONTAINER:
        containers = page.locator(container_sel)
        count = await containers.count()
        if count == 0:
            continue

        for i in range(count):
            try:
                item = containers.nth(i)
                question = await _text_within(item, PAA_QUESTION)

                if not question:
                    try:
                        data_q = await item.get_attribute("data-q", timeout=1000)
                        if data_q:
                            question = data_q.strip()
                    except Exception:
                        pass

                if question:
                    paa = PeopleAlsoAskItem(question=question)
                    if paa.is_valid:
                        items.append(paa)
            except Exception as e:
                logger.debug("Failed to extract PAA item %d: %s", i, e)
                continue

        if items:
            break

    return items


async def _extract_knowledge_panel(page: Page) -> KnowledgePanelItem | None:
    """Extract knowledge panel if present."""
    for container_sel in KP_CONTAINER:
        try:
            container = page.locator(container_sel)
            if await container.count() == 0:
                continue

            title = await _text(page, KP_TITLE)
            if not title:
                continue

            subtitle = await _text(page, KP_SUBTITLE)
            description = await _text(page, KP_DESCRIPTION)

            attributes = {}
            for attr_sel in KP_ATTRIBUTES:
                attr_elements = page.locator(attr_sel)
                attr_count = await attr_elements.count()
                for i in range(attr_count):
                    try:
                        el = attr_elements.nth(i)
                        label = await el.get_attribute("data-attrid", timeout=1000) or ""
                        value = (await el.inner_text(timeout=1000)).strip()
                        if label and value:
                            clean_label = label.split("/")[-1].replace("_", " ").title()
                            attributes[clean_label] = value
                    except Exception:
                        continue

            kp = KnowledgePanelItem(
                title=title,
                subtitle=subtitle,
                description=description,
                entity_type=subtitle,
                attributes=attributes,
            )
            if kp.is_valid:
                return kp
        except Exception as e:
            logger.debug("Failed to extract knowledge panel: %s", e)
            continue

    return None


async def _extract_ads(page: Page) -> list[AdResult]:
    """Extract paid ad results (top and bottom)."""
    results = []

    for container_sels, is_top in [(AD_TOP_CONTAINER, True), (AD_BOTTOM_CONTAINER, False)]:
        for container_sel in container_sels:
            containers = page.locator(container_sel)
            count = await containers.count()
            for i in range(count):
                try:
                    item = containers.nth(i)
                    title = await _text_within(item, AD_TITLE)
                    if not title:
                        continue

                    href = await _attr_within(item, AD_LINK, "href")
                    url = clean_url(href)
                    displayed_url = await _text_within(item, AD_DISPLAYED_URL)
                    description = await _text_within(item, AD_DESCRIPTION)

                    ad = AdResult(
                        position=len(results) + 1,
                        title=title,
                        url=url,
                        displayed_url=displayed_url,
                        description=description,
                        is_top=is_top,
                    )
                    if ad.is_valid:
                        results.append(ad)
                except Exception as e:
                    logger.debug("Failed to extract ad %d: %s", i, e)
                    continue

            if results:
                break

    return results


async def _extract_local_pack(page: Page) -> list[LocalPackResult]:
    """Extract local pack (map 3-pack) results."""
    results = []

    for container_sel in LOCAL_CONTAINER:
        containers = page.locator(container_sel)
        count = await containers.count()
        if count == 0:
            continue

        for i in range(count):
            try:
                item = containers.nth(i)
                name = await _text_within(item, LOCAL_NAME)
                if not name:
                    continue

                rating_text = await _text_within(item, LOCAL_RATING)
                rating = None
                if rating_text:
                    m = re.search(r"([\d,.]+)", rating_text)
                    if m:
                        try:
                            rating = float(m.group(1).replace(",", "."))
                        except ValueError:
                            pass

                reviews_text = await _text_within(item, LOCAL_REVIEWS)
                reviews = None
                if reviews_text:
                    m = re.search(r"\(?([\d,]+)\)?", reviews_text)
                    if m:
                        try:
                            reviews = int(m.group(1).replace(",", ""))
                        except ValueError:
                            pass

                address = await _text_within(item, LOCAL_ADDRESS)
                category = await _text_within(item, LOCAL_CATEGORY)

                lp = LocalPackResult(
                    name=name,
                    rating=rating,
                    reviews=reviews,
                    address=address,
                    category=category,
                )
                if lp.is_valid:
                    results.append(lp)
            except Exception as e:
                logger.debug("Failed to extract local pack item %d: %s", i, e)
                continue

        if results:
            break

    return results


async def _extract_videos(page: Page) -> list[VideoResult]:
    """Extract video carousel results."""
    results = []

    for container_sel in VIDEO_CONTAINER:
        containers = page.locator(container_sel)
        count = await containers.count()
        if count == 0:
            continue

        for i in range(count):
            try:
                item = containers.nth(i)
                title = await _text_within(item, VIDEO_TITLE)
                if not title:
                    continue

                href = await _attr_within(item, VIDEO_LINK, "href")
                url = clean_url(href)
                source = await _text_within(item, VIDEO_SOURCE)
                duration = await _text_within(item, VIDEO_DURATION)
                date = await _text_within(item, VIDEO_DATE)

                video = VideoResult(
                    title=title,
                    url=url,
                    source=source,
                    duration=duration,
                    date=date,
                )
                if video.is_valid:
                    results.append(video)
            except Exception as e:
                logger.debug("Failed to extract video %d: %s", i, e)
                continue

        if results:
            break

    return results


async def _extract_related_searches(page: Page) -> list[RelatedSearch]:
    """Extract related search suggestions from the bottom of the SERP."""
    results = []

    for container_sel in RELATED_CONTAINER:
        container = page.locator(container_sel)
        if await container.count() == 0:
            continue

        for query_sel in RELATED_QUERY:
            query_elements = container.locator(query_sel)
            count = await query_elements.count()
            for i in range(count):
                try:
                    text = (await query_elements.nth(i).inner_text(timeout=1000)).strip()
                    if text:
                        rs = RelatedSearch(query=text)
                        if rs.is_valid:
                            results.append(rs)
                except Exception:
                    continue

            if results:
                break

        if results:
            break

    return results


async def _extract_result_stats(page: Page) -> tuple[str, str]:
    """Extract total results text and search time from the result stats bar."""
    stats_text = await _text(page, RESULT_STATS)
    total = ""
    search_time = ""
    if stats_text:
        count = parse_result_count(stats_text)
        if count is not None:
            total = stats_text.split("(")[0].strip()
        time_val = parse_search_time(stats_text)
        if time_val is not None:
            search_time = f"{time_val}s"
    return total, search_time


# ── Page-level orchestrator ────────────────────────────────────────────────


async def extract_serp_page(
    page: Page,
    query: str,
    page_number: int,
    config: SerpConfig,
) -> SerpPage:
    """Extract all configured SERP features from the current page."""
    serp = SerpPage(query=query, page_number=page_number)

    serp.total_results_text, serp.search_time_text = await _extract_result_stats(page)

    if config.extract_organic:
        try:
            serp.organic = await _extract_organic(page)
        except Exception as e:
            logger.error("Organic extraction failed: %s", e)

    if config.extract_ads:
        try:
            serp.ads = await _extract_ads(page)
        except Exception as e:
            logger.debug("Ad extraction failed: %s", e)

    if config.extract_featured_snippet:
        try:
            serp.featured_snippet = await _extract_featured_snippet(page)
        except Exception as e:
            logger.debug("Featured snippet extraction failed: %s", e)

    if config.extract_people_also_ask:
        try:
            serp.people_also_ask = await _extract_people_also_ask(page)
        except Exception as e:
            logger.debug("PAA extraction failed: %s", e)

    if config.extract_knowledge_panel:
        try:
            serp.knowledge_panel = await _extract_knowledge_panel(page)
        except Exception as e:
            logger.debug("Knowledge panel extraction failed: %s", e)

    if config.extract_local_pack:
        try:
            serp.local_pack = await _extract_local_pack(page)
        except Exception as e:
            logger.debug("Local pack extraction failed: %s", e)

    if config.extract_videos:
        try:
            serp.videos = await _extract_videos(page)
        except Exception as e:
            logger.debug("Video extraction failed: %s", e)

    if config.extract_related_searches:
        try:
            serp.related_searches = await _extract_related_searches(page)
        except Exception as e:
            logger.debug("Related searches extraction failed: %s", e)

    return serp


# ── Query-level scraper ────────────────────────────────────────────────────


async def scrape_query(
    page: Page,
    query: str,
    config: SerpConfig,
) -> SerpResultSet:
    """Scrape one query across configured number of pages."""
    result_set = SerpResultSet()

    for page_num in range(config.max_pages):
        url = config.build_search_url(query, page_num)

        @retry(
            max_attempts=config.max_retries,
            base_delay=config.retry_base_delay,
            max_delay=config.retry_max_delay,
            retryable=(PwTimeout, Exception),
        )
        async def _navigate_and_extract(target_url: str, pn: int) -> SerpPage:
            await page.goto(target_url, timeout=config.timeout_ms)
            await page.wait_for_load_state("domcontentloaded")

            if page_num == 0:
                await dismiss_consent(page)

            if await check_captcha(page):
                raise RuntimeError("CAPTCHA detected — consider using a proxy or increasing delays")

            await page.wait_for_timeout(config.page_load_wait)

            # Wait for organic results to appear
            try:
                await page.wait_for_selector(
                    "div#search, div#rso",
                    state="attached",
                    timeout=10000,
                )
            except PwTimeout:
                logger.warning("No search results container found for page %d", pn)

            return await extract_serp_page(page, query, pn, config)

        try:
            serp_page = await _navigate_and_extract(url, page_num)
            result_set.add_page(serp_page)

            organic_count = len(serp_page.organic)
            sys.stdout.write(f"\r  Page {page_num + 1}: {organic_count} organic results")
            sys.stdout.flush()

            if organic_count == 0:
                logger.info("No organic results on page %d, stopping pagination", page_num + 1)
                break

        except RetryExhausted as e:
            logger.error(
                "Page %d failed after %d retries: %s",
                page_num + 1,
                config.max_retries,
                e.last_error,
            )
            break

        # Delay between pages
        if page_num < config.max_pages - 1:
            delay = human_delay(config.between_pages_min, config.between_pages_max)
            await page.wait_for_timeout(delay)

    print()  # newline after progress
    return result_set
