# Google SERP Scraper

A production-grade, async Google Search Results Page scraper with multi-layer anti-detection, retry logic, and comprehensive SERP feature extraction.

## What it extracts

| Feature | Fields |
|---|---|
| **Organic results** | position, title, URL, displayed URL, description, date, sitelinks |
| **Ads** | position, title, URL, displayed URL, description, top/bottom placement |
| **Featured snippets** | title, URL, content, type (paragraph/list/table) |
| **People Also Ask** | question, answer, source URL, source title |
| **Knowledge panels** | title, subtitle, description, entity type, attributes |
| **Local pack** | name, rating, review count, address, category |
| **Video carousel** | title, URL, source, duration, date |
| **Related searches** | query text |
| **SERP metadata** | total results count, search time |

## Prerequisites

1. **Python 3.11+** via conda
2. **Google Chrome** installed on your system (used for authentic TLS fingerprint)

## Installation

**Step 1** --- Install dependencies:

```bash
pip install playwright pandas openpyxl curl_cffi pytest pytest-asyncio beautifulsoup4
```

**Step 2** --- Install Playwright browsers:

```bash
playwright install chromium
```

Chrome will be used automatically if installed on your system. The scraper falls back to bundled Chromium if Chrome is not found.

## Quick start

Run from the project root directory (`google_maps_business/`):

```bash
# Single query, headless, all output formats
python -m google_search.main -s "best python frameworks" --headless

# View results in the output/ directory
ls output/
```

This creates:
- `output/serp_best_python_frameworks_organic.csv`
- `output/serp_best_python_frameworks_organic.xlsx`
- `output/serp_best_python_frameworks_organic.json`
- `output/serp_best_python_frameworks_full.json`
- `output/serp_best_python_frameworks_full.xlsx`

## Usage

### Single query

```bash
python -m google_search.main -s "plumbers in chicago" --headless
```

### Multiple queries from a file

Create a text file with one query per line:

```
# queries.txt
best plumbers in chicago
emergency plumber near me
plumbing services chicago il
```

Then run:

```bash
python -m google_search.main -i queries.txt --headless
```

### Scrape multiple pages

Scrape up to 3 pages of results per query (max 10):

```bash
python -m google_search.main -s "python frameworks" -p 3 --headless
```

Results are deduplicated across pages automatically.

### Change results per page

Google supports 10, 20, 50, or 100 results per page:

```bash
python -m google_search.main -s "python tutorials" -n 20 --headless
```

### Organic results only (faster)

Skip ads, featured snippets, PAA, knowledge panels, and other features:

```bash
python -m google_search.main -s "python frameworks" --organic-only --headless
```

### Target a specific country and language

```bash
python -m google_search.main -s "best restaurants" --country us --language en --headless
python -m google_search.main -s "mejores restaurantes" --country es --language es --headless
python -m google_search.main -s "beste restaurants" --country de --language de --headless
```

### Choose output format

```bash
# CSV only
python -m google_search.main -s "python" --headless -f csv

# JSON only
python -m google_search.main -s "python" --headless -f json

# Excel only
python -m google_search.main -s "python" --headless -f xlsx

# All formats (default)
python -m google_search.main -s "python" --headless -f all
```

### Custom output directory

```bash
python -m google_search.main -s "python" --headless -o results/my_project/
```

### Use a proxy

```bash
python -m google_search.main -s "python" --headless --proxy "http://user:pass@host:port"
```

For a rotating pool, use `--proxy-file` (one proxy per line, `#` comments allowed) or inline `--proxies "p1,p2,p3"`. Accepted formats and rotation strategies match the Google Maps scraper — see its README's *Proxy rotation* section for the full guide. Environment variables: `SERP_PROXY`, `SERP_PROXY_FILE`, `SERP_PROXY_USERNAME`, `SERP_PROXY_PASSWORD`.

### Run multiple queries in parallel

```bash
python -m google_search.main -i queries.txt --proxy-file proxies.txt -c 4
```

`--concurrency N` (or `-c N`) spawns N parallel workers, each with its own browser process and its own proxy. Queries are pulled from a shared queue, so wall-clock time scales close to linearly in `N`.

**⚠️ Proxies are mandatory when `-c > 1`.** The scraper hard-refuses to start without a proxy pool of at least `N` entries:

```bash
$ python -m google_search.main -i queries.txt -c 4
Error: --concurrency > 1 requires a proxy pool. Pass --proxy-file or --proxies with at least 4 entries (one per worker).
```

Why: N parallel browser sessions hitting Google from one IP get blocked faster than serial — the only safe pattern is one IP per worker. The scraper enforces it. With `-c > 1`, the pool's worker-assignment strategy is forced to `round_robin` so each worker gets a distinct proxy at startup; `--proxy-rotation` still controls within-worker behaviour after blocks.

```bash
# 4 workers, 8-proxy pool, fresh proxy per query inside each worker
python -m google_search.main \
  -i queries.txt \
  --proxy-file proxies-8.txt \
  --proxy-rotation per_query \
  -c 4 \
  --headless \
  -p 2 \
  -o results/
```

Each worker writes its own per-query files, so there is no cross-worker contention.

### Watch the browser (non-headless mode)

Remove `--headless` to see the browser in action (useful for debugging):

```bash
python -m google_search.main -s "python frameworks"
```

### Enable debug logging

```bash
python -m google_search.main -s "python" --headless -v
```

### Safe search

```bash
python -m google_search.main -s "python" --headless --safe
```

## CLI reference

| Flag | Short | Default | Description |
|---|---|---|---|
| `--search` | `-s` | | Search query |
| `--input` | `-i` | | File with queries (one per line) |
| `--pages` | `-p` | `1` | Max result pages per query (1--10) |
| `--num` | `-n` | `10` | Results per page (10, 20, 50, or 100) |
| `--output` | `-o` | `output` | Output directory |
| `--format` | `-f` | `all` | Output format: csv, xlsx, json, or all |
| `--headless` | | off | Run browser without visible GUI |
| `--no-block` | | off | Disable resource blocking (slower but loads full page) |
| `--concurrency` | `-c` | `1` | Parallel workers. **>1 requires a proxy pool with ≥ N entries** |
| `--proxy` | | | Single proxy URL |
| `--proxies` | | | Comma-separated proxy list |
| `--proxy-file` | | | Path to file with one proxy per line (`#` comments ok) |
| `--proxy-username` | | | Default username applied to proxies lacking auth |
| `--proxy-password` | | | Default password applied to proxies lacking auth |
| `--proxy-rotation` | | `sticky` | `sticky`, `round_robin`, `random`, `per_query` |
| `--proxy-max-failures` | | `3` | Consecutive failures before a proxy goes on cooldown |
| `--proxy-cooldown` | | `300` | Cooldown seconds for a failed proxy |
| `--country` | | | Google country code (gl param: us, uk, au, de, etc.) |
| `--language` | | | Google language code (hl param: en, es, fr, de, etc.) |
| `--safe` | | off | Enable safe search |
| `--retries` | | `3` | Max retries per page load |
| `--organic-only` | | off | Only extract organic results (skip all other features) |
| `--verbose` | `-v` | off | Enable debug logging |

## Output files

### Organic export (`_organic.*`)

Flat table with one row per organic result:

| Column | Description |
|---|---|
| `position` | Rank on the SERP (1-indexed) |
| `title` | Page title |
| `url` | Destination URL (cleaned of Google redirects) |
| `displayed_url` | URL as shown on the SERP |
| `description` | Snippet text |
| `date` | Publication date (if shown) |
| `sitelinks_count` | Number of sitelinks |

### Full export (`_full.xlsx`)

Multi-sheet Excel workbook:

| Sheet | Contents |
|---|---|
| Organic | All organic results |
| Ads | Paid results with top/bottom placement |
| People Also Ask | PAA questions |
| Local Pack | Local 3-pack results with ratings |
| Videos | Video carousel entries |
| Related Searches | Related query suggestions |
| Summary | One row per query/page with feature counts |

### Full export (`_full.json`)

Structured JSON with all features per page:

```json
[
  {
    "query": "python frameworks",
    "page_number": 0,
    "total_results_text": "About 1,234,000 results",
    "search_time_text": "0.52s",
    "organic": [...],
    "ads": [...],
    "featured_snippet": {...},
    "people_also_ask": [...],
    "knowledge_panel": {...},
    "local_pack": [...],
    "videos": [...],
    "related_searches": [...]
  }
]
```

## Anti-detection

The scraper uses four layers of anti-detection to avoid being blocked by Google:

### 1. TLS fingerprint (most important)

Standard Playwright uses bundled Chromium, which has a distinct TLS fingerprint (JA3/JA4 hash) that Google can identify. This scraper uses `channel="chrome"` to launch your system's real Chrome binary, which produces an authentic TLS fingerprint identical to regular Chrome users.

### 2. Cookie warming via curl_cffi

Before Playwright opens Google, `curl_cffi` (a Python HTTP client with BoringSSL) makes an initial request to google.com impersonating Chrome's exact TLS stack. The cookies from this authentic TLS session are injected into Playwright, so Google sees session continuity from a "real" browser.

### 3. Browser fingerprint patches

11 JavaScript-level patches applied via `context.add_init_script()`:

- `navigator.webdriver` removal
- `window.chrome` runtime object
- Realistic plugins array (3 plugins)
- Consistent `navigator.languages`
- Permissions API (notification state)
- WebGL vendor/renderer (Apple M1 Pro)
- `navigator.platform` consistency
- `hardwareConcurrency` (8 cores)
- `deviceMemory` (8 GB)
- Network connection API
- Canvas fingerprint noise (subtle alpha channel variation)

### 4. Behavioural signals

- Viewport randomisation (slight variation around 1920x1080)
- Timezone matched to locale (e.g., `en` = `America/Chicago`)
- User-agent rotation (5 realistic strings)
- Triangular-distribution delays (most actions fast, occasional longer pauses)
- Resource blocking hides automation patterns in network waterfalls

## Retry system

Every page navigation is wrapped in a retry decorator with:

- **Exponential backoff**: delays double each attempt (2s, 4s, 8s...)
- **Full jitter**: random delay within the backoff window to avoid thundering herd
- **Configurable**: max attempts, base delay, max delay cap
- **CAPTCHA detection**: if Google shows a CAPTCHA, the scraper logs a warning and stops gracefully
- **Graceful degradation**: if one SERP feature fails to extract, the others still work

## Running the tests

```bash
# From the project root
python -m pytest google_search/tests/ -v
```

107 tests covering config, models, utilities, extraction logic (against real Playwright pages with HTML fixtures), and export functionality. Full suite runs in under 2 seconds.

## Project structure

```
google_search/
    __init__.py          # Package marker
    config.py            # SerpConfig dataclass (28 params)
    models.py            # 10 data models (OrganicResult, AdResult, etc.)
    selectors.py         # CSS selectors with fallbacks per SERP feature
    browser.py           # Stealth Chrome launch + cookie warming + resource blocking
    scraper.py           # Async extraction engine (8 feature extractors)
    utils.py             # URL cleaning, result parsing, delay generation
    export.py            # CSV/XLSX/JSON export with multi-sheet XLSX
    main.py              # Async CLI entry point
    requirements.txt     # Dependencies
    README.md            # This file
    SCRAPER_PROMPT.md    # Reusable prompt for building scrapers like this
    tests/
        __init__.py
        conftest.py      # Shared fixtures
        test_config.py   # 15 tests
        test_models.py   # 28 tests
        test_utils.py    # 17 tests
        test_scraper.py  # 32 tests (Playwright + HTML fixtures)
        test_export.py   # 11 tests
        fixtures/        # Realistic HTML fixtures for each SERP feature
```

## Troubleshooting

**"Error: provide -s SEARCH or -i FILE with queries"**
You need to pass either `-s "your query"` or `-i queries.txt`.

**CAPTCHA detected**
Google has flagged your IP. Options:
- Wait 15--30 minutes and try again
- Use a proxy: `--proxy "http://user:pass@host:port"`
- Reduce request rate by increasing delays in `config.py`

**No results extracted**
- Try running without `--headless` to see what the browser shows
- Enable debug logging with `-v`
- Check if Google is serving a consent page (the scraper handles most locales, but some may be missing)

**Chrome not found**
The scraper falls back to Playwright's bundled Chromium automatically. For best anti-detection, install Google Chrome on your system.

## Disclaimer

This tool is for educational and research purposes. Scraping Google Search results may violate Google's Terms of Service. Use responsibly, respect rate limits, and consider using official APIs (Google Custom Search JSON API) for production workloads.
