"""Utility functions for the SERP scraper."""

import re
from typing import Optional
from urllib.parse import unquote, urlparse, parse_qs

from google_maps.utils import human_delay, clean_filename  # noqa: F401 — re-exported


def clean_url(url: str) -> str:
    """Strip Google redirect wrappers to get the actual destination URL.

    >>> clean_url("/url?q=https://example.com&sa=U&ved=...")
    'https://example.com'
    >>> clean_url("https://example.com/page")
    'https://example.com/page'
    >>> clean_url("")
    ''
    """
    if not url:
        return ""

    if url.startswith("/url?"):
        parsed = parse_qs(urlparse(url).query)
        if "q" in parsed:
            return unquote(parsed["q"][0])

    if url.startswith("https://www.google.com/url?"):
        parsed = parse_qs(urlparse(url).query)
        if "q" in parsed:
            return unquote(parsed["q"][0])
        if "url" in parsed:
            return unquote(parsed["url"][0])

    return url


def parse_result_count(text: str) -> Optional[int]:
    """Parse total result count from Google's result stats text.

    >>> parse_result_count("About 1,234,000 results (0.52 seconds)")
    1234000
    >>> parse_result_count("3 results (0.1 seconds)")
    3
    >>> parse_result_count("")
    """
    if not text:
        return None

    m = re.search(r"([\d,.\s]+)\s*results?", text, re.IGNORECASE)
    if m:
        num_str = m.group(1).replace(",", "").replace(".", "").replace(" ", "")
        try:
            return int(num_str)
        except ValueError:
            pass
    return None


def parse_search_time(text: str) -> Optional[float]:
    """Extract search time in seconds from Google's result stats.

    >>> parse_search_time("About 1,234,000 results (0.52 seconds)")
    0.52
    >>> parse_search_time("")
    """
    if not text:
        return None

    m = re.search(r"\((\d+[.,]\d+)\s*seconds?\)", text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    return None


def strip_tracking_params(url: str) -> str:
    """Remove common tracking parameters from URLs.

    >>> strip_tracking_params("https://example.com/page?utm_source=google&id=123")
    'https://example.com/page?id=123'
    """
    if not url or "?" not in url:
        return url

    tracking_prefixes = ("utm_", "gclid", "fbclid", "msclkid", "dclid")
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    cleaned = {
        k: v for k, v in params.items()
        if not any(k.lower().startswith(p) for p in tracking_prefixes)
    }

    if not cleaned:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    query = "&".join(
        f"{k}={v[0]}" for k, v in cleaned.items()
    )
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{query}"
