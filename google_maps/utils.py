"""Utility functions — URL parsing, filename cleaning, delay generation."""

from __future__ import annotations

import random
import re
from typing import Optional


def coords_from_url(url: str) -> tuple[Optional[float], Optional[float]]:
    """Extract lat/lng from a Google Maps URL.

    Accepts both decimal (`@41.87,-87.63`) and integer (`@41,-87`) coordinate
    forms. Returns ``(None, None)`` when the URL contains no coordinates.

    >>> coords_from_url("https://www.google.com/maps/@41.8781,-87.6298,14z")
    (41.8781, -87.6298)
    >>> coords_from_url("https://example.com")
    (None, None)
    """
    if not url:
        return None, None
    m = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", url)
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            return None, None
    return None, None


def clean_filename(s: str, max_len: int = 100) -> str:
    """Turn arbitrary text into a safe filename.

    >>> clean_filename("plumbers in Chicago!")
    'plumbers_in_Chicago'
    >>> clean_filename("")
    'untitled'
    """
    cleaned = re.sub(r"[^\w\-]+", "_", s.strip()).strip("_")
    if not cleaned:
        return "untitled"
    # After truncation, strip any trailing underscore again so the file name
    # never looks half-chopped.
    return cleaned[:max_len].rstrip("_") or "untitled"


def build_maps_url(center: Optional[str], zoom: int) -> str:
    """Build a Google Maps URL with optional center coordinates.

    Zoom is clamped to the 1-21 range Google supports.

    >>> build_maps_url("41.88,-87.63", 14)
    'https://www.google.com/maps/@41.88,-87.63,14z'
    >>> build_maps_url(None, 14)
    'https://www.google.com/maps'
    >>> build_maps_url("bad", 14)
    'https://www.google.com/maps'
    """
    zoom = max(1, min(21, int(zoom)))
    if center:
        try:
            parts = center.split(",")
            if len(parts) != 2:
                raise ValueError("expected exactly two comma-separated values")
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
                raise ValueError("coordinates out of range")
            return f"https://www.google.com/maps/@{lat},{lng},{zoom}z"
        except (ValueError, IndexError):
            pass
    return "https://www.google.com/maps"


def human_delay(min_ms: int, max_ms: int) -> int:
    """Generate a random delay in ms that mimics human timing.

    Uses a triangular distribution skewed toward the lower end — most actions
    are quick, occasional ones take longer. When ``min_ms == max_ms`` returns
    that value directly (``random.triangular`` raises on a zero-width range).
    """
    if min_ms > max_ms:
        min_ms, max_ms = max_ms, min_ms
    if min_ms == max_ms:
        return int(min_ms)
    mode = min_ms + (max_ms - min_ms) * 0.3
    return int(random.triangular(min_ms, max_ms, mode))


def parse_review_count(raw: str) -> Optional[int]:
    """Extract an integer review count from various Google Maps text formats.

    >>> parse_review_count("(1,234)")
    1234
    >>> parse_review_count("892 reviews")
    892
    >>> parse_review_count("")
    """
    if not raw:
        return None
    m = re.search(r"([\d,]+)", raw)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def parse_rating(raw: str) -> Optional[float]:
    """Extract a float rating value from aria-label text.

    Accepts both `.` and `,` as the decimal separator so non-English locales
    (`"3,8 Sterne"`) are parsed correctly.

    >>> parse_rating("4.5 stars")
    4.5
    >>> parse_rating("3,8 Sterne")
    3.8
    >>> parse_rating("")
    """
    if not raw:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", raw)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    return None


def parse_price_level(raw: str) -> str:
    """Extract price symbols from an aria-label.

    Supports `$`, `£`, `€`, and `¥`.

    >>> parse_price_level("Price: Moderate")
    ''
    >>> parse_price_level("Price: $$$")
    '$$$'
    """
    if not raw:
        return ""
    m = re.search(r"([$£€¥]+)", raw)
    return m.group(1) if m else ""
