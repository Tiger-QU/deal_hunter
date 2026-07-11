# Deal Hunter — ShopBack vs TopCashback

Scrapes cashback rates from ShopBack Australia and TopCashback Australia so
you can check which site (or which other discount) beats the rest before you
buy. Results land in a combined Cursor dashboard plus CSV/JSON files.

## Refresh the data

```bash
python3 scrape_shopback.py       # ~1,400 stores, about 2 minutes
python3 scrape_topcashback.py    # ~1,450 merchants, under a minute
```

Each scraper rebuilds the combined dashboard when it finishes. To rebuild the
dashboard without re-scraping:

```bash
python3 update_dashboard.py
```

No login or API key needed — only the Python standard library is used.

Outputs:

- `data/shopback_deals.json` / `.csv` — ShopBack rates, categories, upsize end times, per-category tiers
- `data/topcashback_deals.json` / `.csv` — TopCashback rates, upsized flags, top-tier labels
- The Cursor dashboard canvas (`shopback-deals.canvas.tsx`) — one row per site,
  grouped by brand, with the better rate marked when a brand is on both

Options (both scrapers):

```bash
python3 scrape_shopback.py --limit 30     # quick test run
python3 scrape_shopback.py --no-canvas    # skip the dashboard update
python3 scrape_shopback.py --workers 8    # be gentler on the site
```

## How it works

**ShopBack** — reads `sitemap.xml` for every store page, then parses the
offer JSON embedded in each page (Next.js RSC payload): display rate, upsized
flag + end time, per-category rates, payout timelines, and a primary category
(ID mapped to a readable name in `UNIVERSAL_CATEGORY_NAMES` inside
`scrape_shopback.py`).

**TopCashback** — scrapes the public category listing pages (63 categories,
paginated) which carry each merchant's name, rate, and "Upsized Offer" flag.
This is deliberate: fetching the ~1,700 individual merchant pages in bulk
makes TopCashback serve a degraded template without the rate card, while the
category listings stay reliable and need only ~200 requests. TopCashback's
fine-grained categories are mapped onto the same coarse groups as ShopBack
(`TCB_CATEGORY_MAP` in `update_dashboard.py`).

**Matching** — `update_dashboard.py` joins the two datasets by normalised
brand name (punctuation, "&"/"and", and words like "Australia" ignored).

Notes:

- Rates shown are standard member rates (not ShopBack Plus).
- Upsize end times in the data are UTC; upsizes usually end at midnight AEST.
- If either site redesigns, the parsers may need updating; each script
  reports pages it failed to parse.


## License
Copyright (c) 2026 Tiger-QU.
Licensed under the [GNU Affero General Public License v3.0](LICENSE).
