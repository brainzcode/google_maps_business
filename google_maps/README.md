# Google Maps Business Scraper

Async, stealth-enabled scraper that extracts business data from Google Maps search results. Built with Playwright and hardened against detection through playwright-stealth, user-agent rotation, human-like timing, per-listing retry logic, block-page detection, and a built-in **proxy pool with four rotation strategies**.

---

## Contents

1. [Data extracted per business](#data-extracted-per-business)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Basic usage](#basic-usage)
5. [CLI reference](#cli-reference)
6. [Proxy rotation — full setup guide](#proxy-rotation--full-setup-guide)
7. [Concurrency — running queries in parallel](#concurrency--running-queries-in-parallel)
8. [Anti-detection measures](#anti-detection-measures)
9. [Architecture](#architecture)
10. [Running tests](#running-tests)
11. [Troubleshooting](#troubleshooting)
12. [Disclaimer](#disclaimer)

---

## Data extracted per business

| Field | Example |
|---|---|
| name | Rescue Plumbing |
| category | Plumber |
| address | 1137 W Webster Ave, Chicago, IL 60614 |
| phone | +17732196071 |
| website | https://www.myrescueplumbing.com/ |
| rating | 4.9 |
| reviews | 1527 |
| price_level | $$ |
| hours | Open 24 hours |
| plus_code | W8CV+H2 Chicago, Illinois |
| latitude | 41.9214708 |
| longitude | -87.6574208 |
| status | Open / Temporarily closed / Permanently closed |
| email | contact@example.com (when published) |
| service_options | Dine-in, Delivery, Takeout |
| url | Full Google Maps listing URL |

## Requirements

- Python 3.11+
- Chromium (installed automatically by Playwright)

## Installation

```bash
pip install playwright playwright-stealth pandas openpyxl
python -m playwright install chromium
python -m google_maps.main --help
```

## Basic usage

Run from the project root (the parent directory that contains the `google_maps/` folder).

```bash
# Single query, visible browser, 50 results
python -m google_maps.main -s "plumbers in Chicago" -t 50

# Headless
python -m google_maps.main -s "dentists in LA" -t 30 --headless

# CSV only
python -m google_maps.main -s "dentists in LA" -t 30 -f csv

# Batch mode — one query per line in searches.txt
python -m google_maps.main -i searches.txt -t 50 -o batch/

# Center the map on specific coordinates + zoom
python -m google_maps.main -s "restaurants" --center "40.7128,-74.0060" --zoom 15

# Verbose logging
python -m google_maps.main -s "plumbers" -v
```

Input files support `#` comments and blank lines. Coordinates are validated (`-90 ≤ lat ≤ 90`, `-180 ≤ lng ≤ 180`) and zoom is clamped to `1-21`.

## CLI reference

| Flag | Short | Default | Description |
|---|---|---|---|
| `--search` | `-s` | | Search query |
| `--input` | `-i` | | File with queries (one per line, `#` comments ok) |
| `--total` | `-t` | `100` | Max results per query |
| `--output` | `-o` | `output` | Output directory |
| `--format` | `-f` | `all` | `csv`, `xlsx`, `json`, or `all` |
| `--center` | | | Map center as `lat,lng` |
| `--zoom` | | `14` | Map zoom level (1-21) |
| `--headless` | | off | Run without a visible browser window |
| `--lang` | | `en` | Browser locale |
| `--retries` | | `3` | Max retries per listing |
| `--verbose` | `-v` | off | Debug logging |
| `--concurrency` | `-c` | `1` | Parallel workers. **>1 requires a proxy pool with ≥ N entries** |
| `--proxy` | | | Single proxy URL |
| `--proxies` | | | Comma-separated list of proxies |
| `--proxy-file` | | | Path to file with one proxy per line |
| `--proxy-username` | | | Default username for proxies lacking auth |
| `--proxy-password` | | | Default password for proxies lacking auth |
| `--proxy-rotation` | | `sticky` | `sticky`, `round_robin`, `random`, `per_query`, `per_listing` |
| `--proxy-max-failures` | | `3` | Consecutive failures before a proxy goes on cooldown |
| `--proxy-cooldown` | | `300` | Cooldown seconds for a failed proxy |

---

## Proxy rotation — full setup guide

This scraper ships with a production-ready proxy pool. You can provide proxies three ways, combine them freely, rotate them under four strategies, and the pool will track health (failures, cooldowns) automatically. A captcha/block page forces an automatic proxy rotation and retry.

### 1. Accepted proxy string formats

Every proxy you pass — whether on the command line, inside `--proxies`, or on a line of `--proxy-file` — must match one of these formats:

```
1.2.3.4:8080                                  # host:port (http assumed)
http://1.2.3.4:8080                           # scheme + host:port
https://1.2.3.4:8443                          # https proxy
socks5://1.2.3.4:1080                         # socks5 proxy
socks4://1.2.3.4:1080                         # socks4 proxy
user:pass@1.2.3.4:8080                        # auth + host:port
http://user:pass@1.2.3.4:8080                 # scheme + auth + host:port
1.2.3.4:8080:user:pass                        # legacy colon-separated form
http://us%40er:p%40ss@1.2.3.4:8080            # URL-encoded credentials
```

Supported schemes: `http`, `https`, `socks4`, `socks5`. If you omit the scheme, `http` is assumed. Credentials are parsed out and passed to Playwright in separate fields, so they never appear in stack traces or error messages.

Rules the parser enforces (anything else → `ValueError` before the browser launches):
- Port must be numeric, `1-65535`
- Host must not be empty
- Surrounding whitespace and paired quotes (`"..."`, `'...'`) are stripped

### 2. Three ways to supply proxies

Pick any one — or combine all three. They're merged (file first, inline second, single last) with duplicates removed.

**Single proxy** — easiest for one-off runs:

```bash
python -m google_maps.main -s "lawyers" --proxy "http://user:pass@1.2.3.4:8080"
```

**Inline list** — a short rotation directly on the CLI:

```bash
python -m google_maps.main -s "cafes" \
  --proxies "1.2.3.4:8080,5.6.7.8:3128,http://u:p@9.9.9.9:8888" \
  --proxy-rotation round_robin
```

**Proxy file** — recommended for production batches. One proxy per line, `#` for comments, blank lines ignored:

```text
# proxies/residential-us.txt
http://user:pass@residential-us-1.mybrand.net:10000
http://user:pass@residential-us-2.mybrand.net:10000
http://user:pass@residential-us-3.mybrand.net:10000
http://user:pass@residential-us-4.mybrand.net:10000
# backup datacenter pool
45.23.87.12:3128
45.23.87.13:3128
```

Then:

```bash
python -m google_maps.main -i queries.txt \
  --proxy-file proxies/residential-us.txt \
  --proxy-rotation per_query
```

### 3. Default credentials for an unauthed list

Most residential providers hand you hostnames and tell you to use a single `user:pass`. Put hostnames-only in the file and pass credentials once:

```text
# proxies.txt
us-east.provider.com:10000
us-west.provider.com:10000
eu-central.provider.com:10000
```

```bash
python -m google_maps.main -i queries.txt \
  --proxy-file proxies.txt \
  --proxy-username acct-42 \
  --proxy-password s3cr3t \
  --proxy-rotation random
```

Credentials already embedded in a proxy line (`user:pass@host:port`) are never overwritten by the CLI defaults.

### 4. Environment variables (no secrets on the CLI)

For CI / cron jobs you can keep secrets out of shell history by exporting:

| Variable | Equivalent flag |
|---|---|
| `GMAPS_PROXY` | `--proxy` |
| `GMAPS_PROXY_FILE` | `--proxy-file` |
| `GMAPS_PROXY_USERNAME` | `--proxy-username` |
| `GMAPS_PROXY_PASSWORD` | `--proxy-password` |

CLI flags override env vars when both are set.

```bash
export GMAPS_PROXY_FILE=./proxies.txt
export GMAPS_PROXY_USERNAME=acct-42
export GMAPS_PROXY_PASSWORD=s3cr3t
python -m google_maps.main -i queries.txt --proxy-rotation per_query
```

### 5. Rotation strategies — when to use each

The pool runs one of five strategies. Pick based on how chatty your proxy provider is and how sensitive the target queries are.

| Strategy | When to use | What it does |
|---|---|---|
| `sticky` (default) | Long batches with a stable proxy provider. Minimises connection churn. | Holds one proxy until it fails, then rotates to a healthy one. |
| `round_robin` | Small, even pool (say 3-10 residentials). Load spread evenly. | Cycles through the list in insertion order. |
| `random` | Large provider-pooled endpoints where request diversity matters. | Picks a healthy proxy uniformly at random on every call. |
| `per_query` | Multi-query batch runs (`-i queries.txt`). | Fresh browser + fresh proxy for each query. Best isolation, highest setup cost. |
| `per_listing` | Heavy targets where even one query can exceed a proxy's quota. | Rotates every single listing extraction (advanced, costly). |

Start with `sticky` for one-off use, jump to `per_query` the moment you're scraping >1 query per run.

### 6. Health tracking and cooldowns

Each proxy has a consecutive-failure counter. Raise it past `--proxy-max-failures` (default 3) and the proxy is benched for `--proxy-cooldown` seconds (default 300s, i.e. 5 min). A successful call resets the counter.

When a captcha / "unusual traffic" page is served the current proxy is marked bad, rotated out, and the query is retried once automatically. If every proxy is in cooldown the pool still hands one back — better to try a warm one than stall the pipeline.

Configure thresholds to match your provider's guidance:

```bash
# Tighter — residential proxy that gets flagged easily
python -m google_maps.main -i queries.txt --proxy-file pool.txt \
  --proxy-max-failures 1 --proxy-cooldown 600

# Looser — datacenter pool that has occasional blips
python -m google_maps.main -i queries.txt --proxy-file pool.txt \
  --proxy-max-failures 10 --proxy-cooldown 60
```

### 7. Residential vs datacenter proxies

| | Residential | Datacenter |
|---|---|---|
| Cost | $$$ per GB | $ per IP/month |
| Block rate on Google | Very low | Medium-high |
| Rotation cost | High latency per rotation (new TCP + TLS) | Low |
| Best strategy | `sticky` or `per_query` | `round_robin` or `random` |
| Typical size | 10s of endpoints (provider rotates behind them) | 100s to 1000s of raw IPs |

If you're running Google Maps at scale, budget for residential. Google is aggressive about blocking datacenter ranges.

### 8. End-to-end production example

```bash
# 1. Write your queries
cat > queries.txt <<EOF
# Chicago home services
plumbers in Chicago
electricians in Chicago
roofers in Chicago
HVAC in Chicago
EOF

# 2. Write your proxy pool
cat > proxies.txt <<EOF
# residential rotating endpoint — 4 sticky sessions
http://us-sess-1:10000@pool.myvendor.io:8000
http://us-sess-2:10000@pool.myvendor.io:8000
http://us-sess-3:10000@pool.myvendor.io:8000
http://us-sess-4:10000@pool.myvendor.io:8000
EOF

# 3. Set credentials out-of-band
export GMAPS_PROXY_USERNAME=acct-42
export GMAPS_PROXY_PASSWORD=$(cat ~/.secrets/proxy-pw)

# 4. Run headless, one proxy per query, Excel + JSON out
python -m google_maps.main \
  -i queries.txt \
  --proxy-file proxies.txt \
  --proxy-rotation per_query \
  --proxy-max-failures 2 \
  --proxy-cooldown 900 \
  --headless \
  -t 100 \
  -o results/chicago/ \
  -f all \
  -v
```

### 9. Debugging a proxy pool

Run with `-v` — every rotation, cooldown, and block-detection event is logged. At the end of the run the scraper prints the final health snapshot:

```
INFO: Final proxy pool status: [
  {'proxy': 'pool.myvendor.io:8000', 'failures': 0, 'cooldown_remaining': 0.0},
  {'proxy': 'pool.myvendor.io:8000', 'failures': 2, 'cooldown_remaining': 877.3}
]
```

Pool-level methods (`ProxyPool.healthy()`, `ProxyPool.status()`) are also available if you embed the scraper as a library.

---

## Concurrency — running queries in parallel

For large query batches you can run multiple workers in parallel with `--concurrency N` (or `-c N`). Each worker is an independent browser process with its own page, its own user-agent, and **its own proxy**. Queries are pulled from a shared queue, so total wall-clock time scales close to linearly in `N` until you saturate CPU/RAM (each Chrome process is roughly 200-400 MB).

### ⚠️ Proxies are mandatory for `-c > 1`

The scraper hard-refuses to start when `--concurrency > 1` without a proxy pool of at least `N` entries:

```bash
$ python -m google_maps.main -i queries.txt -c 4
Error: --concurrency > 1 requires a proxy pool. Pass --proxy-file or --proxies with at least 4 entries (one per worker).

$ python -m google_maps.main -i queries.txt -c 4 --proxies "1.2.3.4:8080,5.6.7.8:3128"
Error: --concurrency=4 requires at least 4 proxies, but the pool has 2. Add more proxies or lower --concurrency.
```

Why the hard gate: N parallel browser sessions from one IP look exactly like a bot to Google and get blocked faster than a single serial run. The only safe pattern is **one IP per worker**, so the scraper enforces it.

### Recommended pattern

1. Build a proxy file with at least one proxy per intended worker — preferably 1.5-2× as many so the pool can rotate around blocks.
2. Pick a workers count that fits both your proxy budget and your machine (`-c 4` is a reasonable starting point on an 8-core laptop).
3. Use `--proxy-rotation per_query` if you want each new query to also hop proxies inside the worker (more isolation, slightly slower).

```bash
# 8 workers, 16-proxy pool, fresh proxy per query within each worker
python -m google_maps.main \
  -i queries.txt \
  --proxy-file proxies-16.txt \
  --proxy-rotation per_query \
  -c 8 \
  --headless \
  -t 100 \
  -o results/
```

### What happens internally

- `--concurrency > 1` overrides the pool's strategy to `round_robin` for **worker-to-proxy assignment** at startup, so the first N proxies are handed out one-per-worker.
- Within each worker the chosen `--proxy-rotation` still controls behaviour for replacements after blocks (`sticky` keeps the assigned proxy until it fails; `per_query` rotates between every query).
- Workers run via `asyncio.gather` on a shared `asyncio.Queue`. When a worker finishes its current query it pulls the next one. Slow queries don't block fast ones.
- A worker that exhausts its proxy retry budget on a query logs the error and moves on — it does not crash the whole run.

### Output files

Each query produces its own `gmaps_<query>.{csv,xlsx,json}` file in `--output`. Workers write independent files, so there is no cross-worker contention.

### Tuning guide

| Workers | RAM (approx) | Min proxies | Notes |
|---|---|---|---|
| 1 | 250 MB | 0 (single proxy optional) | Default. Use for one-off queries. |
| 2-4 | 0.5-1.5 GB | 4-8 | Sweet spot for batches of 10-100 queries. |
| 5-8 | 1.5-3 GB | 8-16 | Hits diminishing returns past 8 on most laptops. |
| 9+ | 3+ GB | 16+ | Server-class. Budget residential proxies accordingly. |

---

## Anti-detection measures

Ordered by impact:

1. **Proxy pool with automatic rotation on block** — the single biggest factor at scale. Captcha / "unusual traffic" pages trigger rotation and retry.
2. **playwright-stealth** patches navigator.webdriver, chrome.runtime, plugins, permissions, WebGL vendor, user-agent data, sec-ch-ua, and 15+ other browser fingerprint signals.
3. **`--disable-blink-features=AutomationControlled`** removes the top-level automation flag.
4. **User-agent rotation** — the context picks randomly from five real Chrome/Safari/Firefox strings per session.
5. **Viewport randomisation** — `1920±20 x 1080±10` so dimensions aren't pixel-identical across runs.
6. **Triangular human-like delays** — most actions are quick, occasional ones pause longer. Better than fixed or uniform random waits.
7. **Consent handling** — consent.google.com redirect and in-page consent overlays are dismissed automatically in English, German, and French.

## Architecture

```
google_maps/
  __init__.py
  main.py          CLI entry point
  config.py        Frozen ScraperConfig dataclass
  models.py        Business + BusinessList (dedup by URL path or name)
  browser.py       Stealth Chromium launch + mid-session relaunch for proxy rotation
  proxy.py         Proxy, parse_proxy_string, ProxyPool (strategies + health)
  scraper.py       Async engine: scroll, click, extract, block detection
  retry.py         Exponential backoff with full-jitter sleep
  export.py        CSV / XLSX / JSON output (pandas)
  utils.py         URL parsing, filename cleaning, delay generation, text parsers
  requirements.txt
  tests/
    test_config.py     ScraperConfig + proxy_strings merging
    test_export.py     CSV / XLSX / JSON round-trip + unicode
    test_main.py       CLI → config plumbing + proxy pool build
    test_models.py     Business validation + dedup
    test_proxy.py      Proxy, parse_proxy_string, ProxyPool strategies + health
    test_retry.py      Retry logic + jitter + backoff cap
    test_scraper.py    Selectors, BlockDetected, detect_block heuristic
    test_utils.py      URL parsing, filenames, delays, rating/review parsers
```

Data flow: `main.run()` → `launch()` (stealth Chromium) → `_load_maps()` (consent, block detection) → for each query: `scrape_query()` → `scroll_listings()` → `extract_business()` per listing → `export()`. On `BlockDetected` the loop marks the proxy bad, calls `relaunch()`, and retries once.

## Running tests

```bash
pip install pytest pytest-asyncio
python -m pytest google_maps/tests/ -v
```

Everything pure-Python (config, export, models, proxy, retry, utils, main helpers, scraper constants + `detect_block`) has 100% branch coverage. The Playwright-dependent async code paths (full scrape flow, consent dismissal, scrolling) are covered by smoke-running against a live Maps page:

```bash
python -m google_maps.main -s "coffee in Portland" -t 5
```

## Troubleshooting

**"Google Maps failed to load after all retries"**
- Check your internet connection.
- Try without `--headless` to watch the browser.
- Behind a corporate firewall? Pass `--proxy`.
- Run with `-v` for detailed logs.

**"Blocked while scraping" / 0 results with a captcha page**
- You're being detected. Add proxies: `--proxy-file proxies.txt --proxy-rotation per_query`.
- Raise the delays in `config.py` (`scroll_delay_min`/`max`, `min_action_delay`/`max`).
- Use residential proxies if you were using datacenter.

**"unsupported proxy scheme" at startup**
- Accepted schemes are `http`, `https`, `socks4`, `socks5`. Correct the proxy string.

**"proxy port not numeric" / "proxy missing port"**
- The parser validates every proxy string before launching. Check for typos — often a stray space or a missing `:port`.

**Results show 0 businesses, no block**
- The query has no Google Maps results — try a different search term or widen the `--zoom`.

**"Executable doesn't exist" on first run**
- Run `python -m playwright install chromium`.

**Slow scrolling**
- The delays between scrolls are intentionally slow (1.8-3.5s) to avoid detection. Tune `scroll_delay_min`/`max` in `config.py`. Going too fast risks blocks.

## Disclaimer

This tool is for educational and research purposes. Check Google's Terms of Service before running large-scale scrapes. Use responsibly — add proxies, respect reasonable delays, and consider the target's published rate limits.
