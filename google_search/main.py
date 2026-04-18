"""Google SERP Scraper — async CLI entry point.

Usage:
    python -m google_search.main -s "best python frameworks" -p 2
    python -m google_search.main -s "plumbers in chicago" --headless -f csv
    python -m google_search.main -i queries.txt -p 3 -o results/ --organic-only
    python -m google_search.main -s "AI news" --country us --language en
    python -m google_search.main -i queries.txt --proxy-file proxies.txt --concurrency 4
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

from google_maps.proxy import Proxy, ProxyPool, parse_proxy_string

from google_search.browser import launch, relaunch
from google_search.config import SerpConfig
from google_search.export import export_full, export_organic
from google_search.scraper import scrape_query
from google_search.utils import clean_filename


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Google SERP Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python -m google_search.main -s "best python frameworks" -p 2
  python -m google_search.main -s "plumbers in chicago" --headless -f csv
  python -m google_search.main -i queries.txt -p 3 -o results/ --organic-only
  python -m google_search.main -s "AI news" --country us --language en -n 20
  python -m google_search.main -s "lawyers near me" --proxy "http://user:pass@host:port"
  python -m google_search.main -i queries.txt --proxy-file proxies.txt --concurrency 4
        """,
    )
    p.add_argument("-s", "--search", help="search query")
    p.add_argument("-i", "--input", help="file with queries, one per line")
    p.add_argument("-p", "--pages", type=int, default=1, help="max result pages per query (default: 1)")
    p.add_argument("-n", "--num", type=int, default=10, choices=[10, 20, 50, 100], help="results per page (default: 10)")
    p.add_argument("-o", "--output", default="output", help="output directory (default: output)")
    p.add_argument("-f", "--format", choices=["csv", "xlsx", "json", "all"], default="all", help="output format (default: all)")
    p.add_argument("--headless", action="store_true", help="run browser without visible GUI")
    p.add_argument("--no-block", action="store_true", help="disable resource blocking (load images, CSS, etc.)")
    p.add_argument("--country", default="", help="Google country code for gl param (e.g. us, uk, au)")
    p.add_argument("--language", default="", help="Google language code for hl param (e.g. en, es, fr)")
    p.add_argument("--safe", action="store_true", help="enable safe search")
    p.add_argument("--retries", type=int, default=3, help="max retries per page load (default: 3)")
    p.add_argument("--organic-only", action="store_true", help="only extract organic results")
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
        choices=["sticky", "round_robin", "random", "per_query"],
        default="sticky",
        help="rotation strategy (default: sticky — hold one until it fails)",
    )
    proxies.add_argument("--proxy-max-failures", type=int, default=3, help="consecutive failures before cooldown (default: 3)")
    proxies.add_argument("--proxy-cooldown", type=float, default=300.0, help="cooldown seconds for failed proxies (default: 300)")

    p.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    return p.parse_args()


def build_config(args: argparse.Namespace) -> SerpConfig:
    organic_only = args.organic_only
    inline = tuple(s.strip() for s in (args.proxies or "").split(",") if s.strip())

    username = args.proxy_username or os.environ.get("SERP_PROXY_USERNAME")
    password = args.proxy_password or os.environ.get("SERP_PROXY_PASSWORD")
    proxy_file = args.proxy_file or os.environ.get("SERP_PROXY_FILE")
    single_proxy = args.proxy or os.environ.get("SERP_PROXY")

    return SerpConfig(
        query=args.search or "",
        input_file=args.input or "",
        max_pages=min(args.pages, 10),
        results_per_page=args.num,
        output_dir=args.output,
        output_format=args.format,
        headless=args.headless,
        proxy=single_proxy,
        proxies=inline,
        proxy_file=proxy_file,
        proxy_username=username,
        proxy_password=password,
        proxy_rotation=args.proxy_rotation,
        proxy_max_failures=args.proxy_max_failures,
        proxy_cooldown_sec=args.proxy_cooldown,
        concurrency=max(1, int(args.concurrency)),
        block_resources=not args.no_block,
        country=args.country,
        language=args.language,
        safe_search=args.safe,
        max_retries=args.retries,
        extract_organic=True,
        extract_ads=not organic_only,
        extract_featured_snippet=not organic_only,
        extract_people_also_ask=not organic_only,
        extract_knowledge_panel=not organic_only,
        extract_related_searches=not organic_only,
        extract_local_pack=not organic_only,
        extract_videos=not organic_only,
    )


def build_proxy_pool(config: SerpConfig) -> Optional[ProxyPool]:
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

    if config.concurrency > 1:
        pool_strategy = "round_robin"
    else:
        pool_strategy = (
            "sticky"
            if config.proxy_rotation in {"sticky", "per_query"}
            else config.proxy_rotation
        )

    return ProxyPool(
        proxies,
        strategy=pool_strategy,
        max_failures=config.proxy_max_failures,
        cooldown_sec=config.proxy_cooldown_sec,
    )


def validate_concurrency(config: SerpConfig, pool: Optional[ProxyPool]) -> None:
    """Refuse to run concurrent workers without enough proxies."""
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


async def _process_query(page, query: str, config: SerpConfig, worker_id: int) -> None:
    """Run a single query end-to-end (scrape + export)."""
    results = await scrape_query(page, query, config)
    if not results:
        print(f"  [w{worker_id}] No results for '{query}'")
        return

    fname = clean_filename(f"serp_{query}")
    all_features = any([
        config.extract_ads,
        config.extract_featured_snippet,
        config.extract_people_also_ask,
        config.extract_knowledge_panel,
        config.extract_related_searches,
        config.extract_local_pack,
        config.extract_videos,
    ])
    if all_features:
        paths = export_full(results, config.output_dir, fname, config.output_format)
    else:
        paths = export_organic(results, config.output_dir, fname, config.output_format)

    prefix = f"[w{worker_id}]" if config.concurrency > 1 else ""
    for p in paths:
        print(f"  {prefix} -> {p}")
    total_organic = len(results.all_organic())
    print(f"  {prefix} {total_organic} organic across {len(results.pages)} page(s) for '{query}'\n")


async def _worker(
    worker_id: int,
    queue: "asyncio.Queue[str]",
    pool: Optional[ProxyPool],
    config: SerpConfig,
) -> None:
    """Pull queries off the queue, scrape, export, repeat."""
    current: Optional[Proxy] = pool.next() if pool else None
    pw, browser, context = await launch(config, proxy=current)
    page = await context.new_page()

    try:
        while True:
            try:
                query = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            try:
                print(f"  [w{worker_id}] start: {query}")
                try:
                    await _process_query(page, query, config, worker_id)
                    if pool is not None and current is not None:
                        pool.mark_good(current)
                except Exception as e:
                    logger.error("[w%d] '%s' failed: %s", worker_id, query, e)
                    if pool is not None and current is not None:
                        pool.mark_bad(current, str(e))
                        # Try a one-shot recovery with a fresh proxy
                        current = pool.next()
                        browser, context = await relaunch(pw, browser, config, current)
                        page = await context.new_page()
            finally:
                queue.task_done()

    finally:
        try:
            await browser.close()
        except Exception:
            pass
        await pw.stop()


async def run(config: SerpConfig) -> None:
    queries = config.queries()
    if not queries:
        print("Error: provide -s SEARCH or -i FILE with queries")
        sys.exit(1)

    pool = build_proxy_pool(config)
    validate_concurrency(config, pool)

    n_workers = min(config.concurrency, len(queries))

    print(f"Queries: {len(queries)} | Pages/query: {config.max_pages} | Results/page: {config.results_per_page}")
    print(f"Output: {config.output_dir}/ | Format: {config.output_format} | Workers: {n_workers}")
    if config.country:
        print(f"Country: {config.country} | Language: {config.language}")
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
