# Google Maps + SERP Scrapers

Two production-grade, async Python scrapers for extracting structured data from Google. One targets **Google Maps** (business listings, contact data, geo), the other targets the **Google Search Results Page** (organic rankings, ads, featured snippets, PAA, local pack, knowledge panels, videos, related searches).

Both are open source, Playwright-based, proxy-pool aware, parallel-worker ready, and hardened against bot detection with real Chrome TLS fingerprints, cookie warming, stealth patches, and human-like timing.

Built and maintained by [Luminous Digital Visions](https://luminousdigitalvisions.com).

---

## The two crawlers

| | [Google Maps Business Scraper](./google_maps/README.md) | [Google SERP Scraper](./google_search/README.md) |
|---|---|---|
| **Use case** | Lead generation, local competitor mapping, address/phone enrichment | Rank tracking, SERP feature monitoring, content gap research, PAA mining |
| **Output per record** | name, category, address, phone, website, rating, reviews, price level, hours, plus code, lat/lng, status, email, service options, listing URL | position, title, URL, displayed URL, description, date, sitelinks, plus ads / snippets / PAA / knowledge panel / local pack / videos / related searches |
| **Formats** | CSV, XLSX, JSON | CSV, XLSX (multi-sheet), JSON |
| **Query input** | `-s "query"` or `-i queries.txt` | `-s "query"` or `-i queries.txt` |
| **Paging** | Lazy scroll until `--total` hit | 1–10 result pages, 10/20/50/100 per page |
| **Geo targeting** | `--center lat,lng` + `--zoom 1-21` | `--country us` + `--language en` |
| **Proxy rotation** | sticky, round_robin, random, per_query, per_listing | sticky, round_robin, random, per_query |
| **Parallel workers** | `-c N` (requires N proxies) | `-c N` (requires N proxies) |
| **Run** | `python -m google_maps.main -s "plumbers in Chicago" -t 50` | `python -m google_search.main -s "best python frameworks" -p 2` |

Head to the folder READMEs for the full CLI reference, proxy guide, concurrency rules, anti-detection layers, and troubleshooting:

- [`google_maps/README.md`](./google_maps/README.md) — Google Maps Business Scraper
- [`google_search/README.md`](./google_search/README.md) — Google SERP Scraper

A full walkthrough tutorial lives in [`content/scrape-google-maps-tutorial.md`](./content/scrape-google-maps-tutorial.md).

---

## Requirements

- Python 3.11+ (install via conda recommended)
- Google Chrome on your system (for authentic TLS fingerprint in the SERP scraper; the Maps scraper runs on bundled Chromium)

## Install both

```bash
pip install playwright playwright-stealth pandas openpyxl curl_cffi beautifulsoup4 pytest pytest-asyncio
python -m playwright install chromium
```

Run either scraper as a module from the repo root:

```bash
python -m google_maps.main --help
python -m google_search.main --help
```

## Quick tour

```bash
# Scrape 50 plumber listings in Chicago (Maps)
python -m google_maps.main -s "plumbers in Chicago" -t 50

# Pull the top 2 SERP pages for a keyword, organic results only (Search)
python -m google_search.main -s "emergency plumber near me" -p 2 --organic-only

# Batch mode — queries from a file, 4 parallel workers, residential proxy pool
python -m google_maps.main \
  -i queries.txt \
  --proxy-file proxies.txt \
  --proxy-rotation per_query \
  -c 4 \
  --headless \
  -t 100 \
  -o results/
```

## What you get for free

- **Proxy pool with health tracking** — 5 accepted proxy string formats, 4–5 rotation strategies, per-proxy failure counters, automatic cooldown, automatic rotation on block/captcha.
- **Parallel workers** with a hard 1:1 worker-to-proxy safety gate so you can't accidentally burn an IP by launching N browsers behind it.
- **Anti-detection stack** — real Chrome binary for authentic TLS (SERP), `curl_cffi` cookie warming (SERP), 11 JavaScript fingerprint patches (SERP), `playwright-stealth` (Maps), user-agent rotation, viewport jitter, triangular human-like delays, multi-locale consent handling.
- **Retry logic** — exponential backoff with full jitter, per-page or per-listing, configurable max attempts and caps.
- **Clean, typed output** — frozen dataclass configs, dataclass data models, deduplication by URL, multi-format export (CSV / XLSX / JSON) including multi-sheet Excel workbooks.
- **Test suite** — 100+ tests across both crawlers covering config, models, proxy pool, retries, extraction (HTML fixtures), and export.

## Repo structure

```
google_maps_business/
├── google_maps/          Google Maps Business Scraper (Python module)
├── google_search/        Google SERP Scraper (Python module)
├── content/              Tutorial article(s)
├── output/               Sample output files
├── booking.com/          Booking.com scraper (separate project)
├── scraper/              Legacy scraper code
└── README.md             You are here
```

---

## Coming soon — Luminous Lead Studio

We are building a full lead generation and SEO studio on top of these crawlers: end-to-end pipeline for any industry, covering lead discovery, enrichment, outreach automation, a complete technical SEO audit, and advanced competitor analysis. One platform, data in and revenue out.

**Join the waitlist at [luminousdigitalvisions.com](https://luminousdigitalvisions.com).**

---

## Contributing

Issues and PRs welcome at [github.com/brainzcode/google_maps_business](https://github.com/brainzcode/google_maps_business). Please keep the architecture shape (frozen config dataclass → models → scraper → export) and add tests for new behaviour.

## License & responsible use

Educational and research purposes. Check Google's Terms of Service before running at scale. Use residential proxies, keep delays sane, and consider official APIs (Places API, Custom Search JSON API) for production workloads.

— [Luminous Digital Visions](https://luminousdigitalvisions.com)
