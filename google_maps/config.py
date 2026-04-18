"""Scraper configuration with sensible defaults and anti-ban tuning."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ScraperConfig:
    """Immutable configuration for a scrape session."""

    # Search
    query: str = ""
    input_file: str = ""
    max_results: int = 100

    # Output
    output_dir: str = "output"
    output_format: str = "all"  # csv | xlsx | json | all

    # Map positioning
    center: Optional[str] = None  # "lat,lng"
    zoom: int = 14

    # Browser
    headless: bool = True
    locale: str = "en"
    timeout_ms: int = 60_000

    # Single-proxy shortcut. `proxies` / `proxy_file` take precedence if set.
    proxy: Optional[str] = None  # "http://user:pass@host:port"

    # Proxy pool
    proxies: tuple[str, ...] = field(default_factory=tuple)
    proxy_file: Optional[str] = None
    proxy_username: Optional[str] = None  # Applied to all pool entries lacking auth
    proxy_password: Optional[str] = None
    proxy_rotation: str = "sticky"  # sticky | round_robin | random | per_query | per_listing
    proxy_max_failures: int = 3
    proxy_cooldown_sec: float = 300.0

    # Concurrency — number of parallel workers. >1 requires a proxy pool with
    # at least this many entries (enforced at startup).
    concurrency: int = 1

    # Anti-ban timing (milliseconds)
    min_action_delay: int = 400
    max_action_delay: int = 1200
    scroll_delay_min: int = 1800
    scroll_delay_max: int = 3500
    page_load_wait: int = 2500

    # Retry
    max_retries: int = 3
    retry_base_delay: float = 1.0  # seconds
    retry_max_delay: float = 30.0  # seconds

    # Scroll stale threshold — stop after this many scroll cycles with no new results
    scroll_stale_limit: int = 5

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

        Order of precedence:
            1. `query` set explicitly via --search
            2. `input_file` (one query per line, blanks + `#` comments skipped)
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
        """Combine `proxy`, `proxies`, and `proxy_file` into a single list.

        Returns the merged list in the order:
            1. `proxy_file` entries (one per line, `#` comments ignored)
            2. `proxies` tuple entries
            3. single `proxy` string (backward-compat)
        Duplicates preserving first occurrence.
        """
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
