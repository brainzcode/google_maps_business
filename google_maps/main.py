#!/usr/bin/env python3
"""
Google Maps Business Scraper

Async, stealth scraper with retry logic that extracts all available business
data from Google Maps search results. Supports configurable start location,
zoom, headless mode, multiple output formats, batch input, proxy rotation,
and parallel-worker concurrency.

Usage:
    python -m google_maps.main -s "plumbers in Chicago" -t 50
    python -m google_maps.main -i searches.txt -t 20 -o results/ -f csv
    python -m google_maps.main -s "lawyers" --proxy "http://user:pass@host:port"
    python -m google_maps.main -i queries.txt --proxy-file proxies.txt --concurrency 4
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

from playwright.async_api import TimeoutError as PwTimeout

from google_maps.browser import launch, relaunch
from google_maps.config import ScraperConfig
from google_maps.export import export
from google_maps.proxy import Proxy, ProxyPool, parse_proxy_string
from google_maps.scraper import BlockDetected, SEARCHBOX, scrape_query
from google_maps.utils import build_maps_url, clean_filename

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Google Maps Business Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python -m google_maps.main -s "plumbers in Chicago" -t 50
  python -m google_maps.main -s "restaurants" --center "40.71,-74.00" --zoom 12 -t 100
  python -m google_maps.main -i searches.txt -t 20 -o results/ -f csv
  python -m google_maps.main -s "dentists in LA" --headless -f json
  python -m google_maps.main -s "lawyers" --proxy "http://user:pass@host:port"
  python -m google_maps.main -i searches.txt --proxy-file proxies.txt --proxy-rotation per_query
  python -m google_maps.main -i queries.txt --proxy-file proxies.txt --concurrency 4
        """,
    )
    p.add_argument("-s", "--search", help="search query")
    p.add_argument("-i", "--input", help="file with queries, one per line")
    p.add_argument("-t", "--total", type=int, default=100, help="max results per query (default: 100)")
    p.add_argument("-o", "--output", default="output", help="output directory (default: output)")
    p.add_argument("-f", "--format", choices=["csv", "xlsx", "json", "all"], default="all", help="output format (default: all)")
    p.add_argument("--center", help="center map on lat,lng before searching, e.g. '40.71,-74.00'")
    p.add_argument("--zoom", type=int, default=14, help="map zoom level 1-21 (default: 14)")
    p.add_argument("--headless", action="store_true", help="run browser without visible GUI")
    p.add_argument("--lang", default="en", help="browser locale (default: en)")
    p.add_argument(
        "-c", "--concurrency",
        type=int,
        default=1,
        help="parallel workers (default: 1; >1 REQUIRES --proxy-file or --proxies with >= concurrency entries)",
    )

    proxies = p.add_argument_group("proxy options (combine any of these)")
    proxies.add_argument("--proxy", help="single proxy, e.g. 'http://user:pass@host:port'")
    proxies.add_argument("--proxies", help="comma-separated proxy list")
    proxies.add_argument("--proxy-file", help="path to file with one proxy per line (# comments allowed)")
    proxies.add_argument("--proxy-username", help="default username applied to proxies lacking auth")
    proxies.add_argument("--proxy-password", help="default password applied to proxies lacking auth")
    proxies.add_argument(
        "--proxy-rotation",
        choices=["sticky", "round_robin", "random", "per_query", "per_listing"],
        default="sticky",
        help="rotation strategy (default: sticky — hold one until it fails)",
    )
    proxies.add_argument("--proxy-max-failures", type=int, default=3, help="consecutive failures before cooldown (default: 3)")
    proxies.add_argument("--proxy-cooldown", type=float, default=300.0, help="cooldown seconds for failed proxies (default: 300)")

    p.add_argument("--retries", type=int, default=3, help="max retries per listing (default: 3)")
    p.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    return p.parse_args()


def build_config(args: argparse.Namespace) -> ScraperConfig:
    inline = tuple(s.strip() for s in (args.proxies or "").split(",") if s.strip())

    username = args.proxy_username or os.environ.get("GMAPS_PROXY_USERNAME")
    password = args.proxy_password or os.environ.get("GMAPS_PROXY_PASSWORD")
    proxy_file = args.proxy_file or os.environ.get("GMAPS_PROXY_FILE")
    single_proxy = args.proxy or os.environ.get("GMAPS_PROXY")

    return ScraperConfig(
        query=args.search or "",
        input_file=args.input or "",
        max_results=args.total,
        output_dir=args.output,
        output_format=args.format,
        center=args.center,
        zoom=args.zoom,
        headless=args.headless,
        locale=args.lang,
        concurrency=max(1, int(args.concurrency)),
        proxy=single_proxy,
        proxies=inline,
        proxy_file=proxy_file,
        proxy_username=username,
        proxy_password=password,
        proxy_rotation=args.proxy_rotation,
        proxy_max_failures=args.proxy_max_failures,
        proxy_cooldown_sec=args.proxy_cooldown,
        max_retries=args.retries,
    )


def build_proxy_pool(config: ScraperConfig) -> Optional[ProxyPool]:
    """Assemble a ProxyPool from all configured sources, or return None."""
    raw = config.proxy_strings()
    if not raw:
        return None

    proxies: list[Proxy] = []
    for s in raw:
        p = parse_proxy_string(s)
        if p.username is None and config.proxy_username:
            p = Proxy(p.server, config.proxy_username, config.proxy_password)
        proxies.append(p)

    # When concurrency > 1, force round_robin so each worker gets a distinct
    # proxy at startup. Within-worker rotation still respects user choice.
    if config.concurrency > 1:
        pool_strategy = "round_robin"
    else:
        pool_strategy = (
            "sticky"
            if config.proxy_rotation in {"sticky", "per_query", "per_listing"}
            else config.proxy_rotation
        )

    return ProxyPool(
        proxies,
        strategy=pool_strategy,
        max_failures=config.proxy_max_failures,
        cooldown_sec=config.proxy_cooldown_sec,
    )


def validate_concurrency(config: ScraperConfig, pool: Optional[ProxyPool]) -> None:
    """Raise SystemExit if concurrency is requested without a sufficient pool.

    Concurrency > 1 from a single IP gets blocked faster than serial. We
    enforce a 1:1 worker-to-proxy minimum so users can't shoot themselves in
    the foot.
    """
    if config.concurrency <= 1:
        return
    if pool is None:
        print(
            "Error: --concurrency > 1 requires a proxy pool. "
            "Pass --proxy-file or --proxies with at least "
            f"{config.concurrency} entries (one per worker).",
            file=sys.stderr,
        )
        sys.exit(2)
    if pool.size < config.concurrency:
        print(
            f"Error: --concurrency={config.concurrency} requires at least "
            f"{config.concurrency} proxies, but the pool has {pool.size}. "
            "Add more proxies or lower --concurrency.",
            file=sys.stderr,
        )
        sys.exit(2)


async def _load_maps(page, config: ScraperConfig) -> bool:
    """Navigate to Google Maps and dismiss consent. Returns True if ready."""
    from google_maps.scraper import detect_block

    url = build_maps_url(config.center, config.zoom)

    for attempt in range(1, config.max_retries + 1):
        try:
            await page.goto(url, timeout=config.timeout_ms, wait_until="domcontentloaded")
        except PwTimeout:
            logger.warning("Page load timed out (attempt %d/%d)", attempt, config.max_retries)
            continue
        except Exception as e:
            logger.warning("Page load error (attempt %d/%d): %s", attempt, config.max_retries, e)
            continue

        await page.wait_for_timeout(3000)

        if await detect_block(page):
            raise BlockDetected("Google block detected on initial load")

        if "consent.google" in page.url:
            logger.info("Consent page detected, dismissing...")
            for btn_text in ["Accept all", "Reject all", "Alle akzeptieren", "Tout accepter"]:
                try:
                    await page.click(f'button:has-text("{btn_text}")', timeout=3000)
                    await page.wait_for_url("**/maps/**", timeout=15000)
                    await page.wait_for_timeout(3000)
                    break
                except PwTimeout:
                    continue

        for btn_text in ["Accept all", "Reject all", "I agree"]:
            try:
                await page.click(f'button:has-text("{btn_text}")', timeout=1000)
                await page.wait_for_timeout(1000)
                break
            except PwTimeout:
                continue

        try:
            await page.wait_for_selector(SEARCHBOX, timeout=15000)
            return True
        except PwTimeout:
            logger.warning(
                "Search box not found (attempt %d/%d), URL: %s",
                attempt, config.max_retries, page.url,
            )

    return False


def _print_query_result(worker_id: int, query: str, results, config: ScraperConfig) -> None:
    if results:
        fname = clean_filename(f"gmaps_{query}")
        paths = export(results, config.output_dir, fname, config.output_format)
        prefix = f"[w{worker_id}]" if config.concurrency > 1 else ""
        for p in paths:
            print(f"  {prefix} -> {p}")
        print(f"  {prefix} Total: {len(results)} businesses for '{query}'\n")
    else:
        print(f"  [w{worker_id}] No businesses extracted for '{query}'\n")


async def _worker(
    worker_id: int,
    queue: "asyncio.Queue[str]",
    pool: Optional[ProxyPool],
    config: ScraperConfig,
) -> None:
    """Worker loop: pull queries off the queue, scrape, export, repeat."""
    current: Optional[Proxy] = pool.next() if pool else None
    pw, browser, context = await launch(config, proxy=current)
    page = await context.new_page()

    try:
        # Load Maps with automatic proxy rotation on block
        attempts_left = max(1, pool.size if pool else 1)
        ready = False
        while attempts_left > 0 and not ready:
            attempts_left -= 1
            try:
                if await _load_maps(page, config):
                    ready = True
                    break
                if pool is not None and current is not None:
                    pool.mark_bad(current, "maps load failed")
                    current = pool.next()
                    browser, context = await relaunch(pw, browser, config, current)
                    page = await context.new_page()
                    continue
                logger.error("[w%d] Maps failed to load and no proxy pool to rotate", worker_id)
                return
            except BlockDetected as e:
                logger.warning("[w%d] Block on initial load: %s", worker_id, e)
                if pool is None or current is None:
                    return
                pool.mark_bad(current, str(e))
                current = pool.next()
                browser, context = await relaunch(pw, browser, config, current)
                page = await context.new_page()

        if not ready:
            logger.error("[w%d] Maps failed to load after exhausting proxies", worker_id)
            return

        while True:
            try:
                query = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            try:
                print(f"  [w{worker_id}] start: {query}")
                results = None
                for tries in range(2):
                    try:
                        results = await scrape_query(page, query, config)
                        if pool is not None and current is not None:
                            pool.mark_good(current)
                        break
                    except BlockDetected as e:
                        logger.warning("[w%d] Block during '%s': %s", worker_id, query, e)
                        if pool is None or current is None or tries == 1:
                            print(f"  [w{worker_id}] blocked: {query}")
                            break
                        pool.mark_bad(current, str(e))
                        current = pool.next()
                        browser, context = await relaunch(pw, browser, config, current)
                        page = await context.new_page()
                        if not await _load_maps(page, config):
                            break

                _print_query_result(worker_id, query, results, config)

                # Reset search box for next iteration
                try:
                    box = page.locator(SEARCHBOX)
                    await box.click()
                    await box.fill("")
                except Exception:
                    await page.goto(build_maps_url(config.center, config.zoom), timeout=config.timeout_ms)
                    await page.wait_for_load_state("domcontentloaded")
            finally:
                queue.task_done()

    finally:
        try:
            await browser.close()
        except Exception:
            pass
        await pw.stop()


async def run(config: ScraperConfig) -> None:
    queries = config.queries()
    if not queries:
        print("Error: provide -s SEARCH or -i FILE")
        sys.exit(1)

    pool = build_proxy_pool(config)
    validate_concurrency(config, pool)

    n_workers = min(config.concurrency, len(queries))

    print(f"Queries: {len(queries)} | Max/query: {config.max_results} | Format: {config.output_format}")
    print(f"Output: {config.output_dir}/ | Headless: {config.headless} | Workers: {n_workers}")
    if config.center:
        print(f"Center: {config.center} | Zoom: {config.zoom}")
    if pool is not None:
        print(f"Proxies: {pool.size} | Rotation: {config.proxy_rotation}")
    print()

    queue: asyncio.Queue[str] = asyncio.Queue()
    for q in queries:
        queue.put_nowait(q)

    workers = [
        asyncio.create_task(_worker(i + 1, queue, pool, config))
        for i in range(n_workers)
    ]
    await asyncio.gather(*workers, return_exceptions=False)

    if pool is not None:
        logger.info("Final proxy pool status: %s", pool.status())

    print("Done.")


def main() -> None:
    args = parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    config = build_config(args)
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
