"""SERP scraper configuration with sensible defaults and anti-ban tuning."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote_plus


@dataclass(frozen=True)
class SerpConfig:
    """Immutable configuration for a SERP scrape session."""

    # Search
    query: str = ""
    input_file: str = ""
    max_pages: int = 1
    results_per_page: int = 10

    # Output
    output_dir: str = "output"
    output_format: str = "all"  # csv | xlsx | json | all

    # Browser
    headless: bool = True
    locale: str = "en"
    timeout_ms: int = 60_000
    block_resources: bool = True

    # Single-proxy shortcut. `proxies` / `proxy_file` take precedence if set.
    proxy: Optional[str] = None

    # Proxy pool
    proxies: tuple[str, ...] = field(default_factory=tuple)
    proxy_file: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    proxy_rotation: str = "sticky"  # sticky | round_robin | random | per_query
    proxy_max_failures: int = 3
    proxy_cooldown_sec: float = 300.0

    # Concurrency — number of parallel workers. >1 requires a proxy pool with
    # at least this many entries (enforced at startup).
    concurrency: int = 1

    # Anti-ban timing (milliseconds)
    min_action_delay: int = 800
    max_action_delay: int = 2500
    page_load_wait: int = 3000
    between_pages_min: int = 2000
    between_pages_max: int = 5000

    # Retry
    max_retries: int = 3
    retry_base_delay: float = 2.0
    retry_max_delay: float = 30.0

    # Google search parameters
    country: str = ""   # gl param (us, uk, au, etc.)
    language: str = ""  # hl param (en, es, fr, etc.)
    safe_search: bool = False

    # Feature toggles
    extract_organic: bool = True
    extract_ads: bool = True
    extract_featured_snippet: bool = True
    extract_people_also_ask: bool = True
    extract_knowledge_panel: bool = True
    extract_related_searches: bool = True
    extract_local_pack: bool = True
    extract_videos: bool = True

    # User agents to rotate through
    user_agents: tuple[str, ...] = field(default_factory=lambda: (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    ))

    def queries(self) -> list[str]:
        """Return the list of queries to run.

        Reads `query` first, falling back to `input_file`. Blank lines and
        `#` comments in the file are ignored. UTF-8 encoded.
        """
        if self.query:
            return [self.query]
        if self.input_file:
            if not os.path.isfile(self.input_file):
                raise FileNotFoundError(f"input file not found: {self.input_file}")
            with open(self.input_file, encoding="utf-8") as f:
                return [
                    stripped
                    for raw in f
                    if (stripped := raw.split("#", 1)[0].strip())
                ]
        return []

    def proxy_strings(self) -> list[str]:
        """Combine `proxy`, `proxies`, and `proxy_file` into a deduped list."""
        merged: list[str] = []
        seen: set[str] = set()

        if self.proxy_file:
            if not os.path.isfile(self.proxy_file):
                raise FileNotFoundError(f"proxy file not found: {self.proxy_file}")
            with open(self.proxy_file, encoding="utf-8") as f:
                for raw in f:
                    line = raw.split("#", 1)[0].strip()
                    if line and line not in seen:
                        merged.append(line)
                        seen.add(line)

        for s in self.proxies:
            if s and s not in seen:
                merged.append(s)
                seen.add(s)

        if self.proxy and self.proxy not in seen:
            merged.append(self.proxy)
            seen.add(self.proxy)

        return merged

    def build_search_url(self, query: str, page: int = 0) -> str:
        """Build a Google search URL with configured parameters.

        Args:
            query: The search query string.
            page: Zero-indexed page number (0 = first page).
        """
        params = [f"q={quote_plus(query)}"]

        if self.results_per_page != 10:
            params.append(f"num={self.results_per_page}")

        if page > 0:
            params.append(f"start={page * self.results_per_page}")

        if self.country:
            params.append(f"gl={quote_plus(self.country)}")

        if self.language:
            params.append(f"hl={quote_plus(self.language)}")

        if self.safe_search:
            params.append("safe=active")

        return f"https://www.google.com/search?{'&'.join(params)}"
