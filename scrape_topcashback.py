#!/usr/bin/env python3
"""Scrape TopCashback Australia cashback rates for all merchants.

Works without login. Merchant rates are collected from the public category
listing pages (63 categories, paginated, 25 merchants per page) rather than
the individual merchant pages: the listings are complete, include the rate
and "Upsized Offer" flag, and need ~200 requests instead of ~1,700 (the
per-merchant pages start serving a degraded template without the rate card
when fetched in bulk).

Outputs:
  data/topcashback_deals.json
  data/topcashback_deals.csv
  then rebuilds the combined dashboard canvas (see update_dashboard.py)

Usage:
  python3 scrape_topcashback.py                # full run, ~1 minute
  python3 scrape_topcashback.py --no-canvas    # skip dashboard update
"""

import argparse
import concurrent.futures
import csv
import datetime
import html as html_lib
import json
import math
import re
import sys
import threading
import time
import urllib.request
from pathlib import Path

BASE = "https://www.topcashback.com.au"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-AU,en;q=0.9",
}
OUT_DIR = Path(__file__).resolve().parent / "data"
PAGE_SIZE = 25
MIN_MERCHANT_HTML = 15000


def is_blocked(html):
    """TopCashback serves a tiny AWS WAF page when rate-limited."""
    return (
        len(html) < MIN_MERCHANT_HTML
        or "awsWaf" in html
        or re.search(r"<title>\s*</title>", html[:2500])
    )


def fetch(url, timeout=30, retries=3, backoff=2.0):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001 - retry any network error
            last_err = e
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def parse_merchant_tiers(html):
    """Extract per-category rates from a merchant page rate card."""
    start = html.find('<div class="merch-rate-card">')
    if start < 0:
        return []

    end = html.find('<div class="merch-secondary-slice"', start)
    section = html[start : end if end > start else start + 12000]

    tiers = []
    for block in re.split(r'<span class="merch-cat__sub-cat">', section)[1:]:
        label = re.search(r"^([^<]+)", block)
        rate = re.search(r'merch-cat__rate">([^<]+)<', block)
        if not label or not rate:
            continue
        tiers.append({
            "label": html_lib.unescape(label.group(1).strip()),
            "rate": html_lib.unescape(rate.group(1).strip()),
        })
    return tiers


def fetch_merchant_tiers(slug, delay=0.0):
    """Fetch one merchant page and return its tier breakdown."""
    if delay:
        time.sleep(delay)
    url = f"{BASE}/{slug}/"
    html = fetch(url, retries=4, backoff=3.0)
    if is_blocked(html):
        return []
    return parse_merchant_tiers(html)


def needs_tier_enrichment(merchant):
    """Only merchants with variable rates need a merchant-page fetch."""
    return "up to" in (merchant.get("cashback") or "").lower()


def enrich_merchants(merchants, workers=2, delay=0.8, limit=None):
    """Add per-category tiers by visiting merchant pages with 'Up to' rates."""
    for merchant in merchants:
        merchant.setdefault("tiers", [])

    targets = [m for m in merchants if needs_tier_enrichment(m)]
    if limit:
        targets = targets[:limit]
    lock = threading.Lock()
    last_fetch = {"t": 0.0}
    done = 0
    blocked = 0
    with_tiers = 0

    def enrich_one(merchant):
        nonlocal done, blocked, with_tiers
        with lock:
            wait = max(0.0, delay - (time.time() - last_fetch["t"]))
            if wait:
                time.sleep(wait)
            last_fetch["t"] = time.time()

        try:
            tiers = fetch_merchant_tiers(merchant["slug"], delay=0)
        except Exception:
            tiers = []

        merchant["tiers"] = tiers
        with lock:
            done += 1
            if tiers:
                with_tiers += 1
            else:
                blocked += 1
            if done % 50 == 0 or done == len(targets):
                print(
                    f"  {done}/{len(targets)} merchant pages enriched "
                    f"({with_tiers} with tiers)",
                    flush=True,
                )
        return merchant

    if not targets:
        print("  no 'Up to' merchants to enrich", flush=True)
        return 0

    print(
        f"Enriching {len(targets)} 'Up to' merchant pages "
        f"({workers} workers, {delay:.1f}s gap)...",
        flush=True,
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(enrich_one, targets))
    return blocked


def get_category_slugs():
    xml = fetch(BASE + "/sitemap.xml")
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    slugs = []
    for loc in locs:
        m = re.match(rf"{BASE}/category/([a-z0-9-]+)/", loc)
        if m:
            slugs.append(m.group(1))
    return sorted(set(slugs))


def pretty_category(slug):
    words = slug.replace("-", " ").split()
    small = {"and", "of", "the"}
    return " ".join(
        w if w in small else ("PAYG" if w == "payg" else w.capitalize())
        for w in words
    )


def parse_category_page(html):
    """Yield (slug, name, rate, upsized) for each merchant card."""
    cards = re.findall(
        r'<a href="/([a-z0-9-]+)/"[^>]*class="category-panel"(.*?)</a>',
        html,
        re.S,
    )
    out = []
    for slug, body in cards:
        name = re.search(r'search-merchant-name">([^<]+)<', body)
        rate = re.search(r'category-cashback-rate[^>]*>([^<]+)<', body)
        flag = re.search(r'search-exclusive-text">([^<]+)<', body)
        if not rate:
            continue
        out.append({
            "slug": slug,
            "name": html_lib.unescape(name.group(1)).strip() if name else slug,
            "cashback": html_lib.unescape(rate.group(1)).strip(),
            "upsized": bool(flag and "Upsized" in flag.group(1)),
        })
    return out


def result_count(html):
    m = re.search(r"1 - \d+ of (\d+) results", html)
    return int(m.group(1)) if m else None


def scrape_category(cat_slug):
    """Return all merchant cards across the category's pages."""
    first = fetch(f"{BASE}/category/{cat_slug}/")
    cards = parse_category_page(first)
    total = result_count(first)
    pages = math.ceil(total / PAGE_SIZE) if total else 1
    for page in range(2, pages + 1):
        html = fetch(f"{BASE}/category/{cat_slug}/?page={page}")
        cards.extend(parse_category_page(html))
    return cards


def scrape_all(cat_slugs, workers=6):
    merchants = {}
    errors = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(scrape_category, c): c for c in cat_slugs}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            cat = futures[fut]
            done += 1
            try:
                for card in fut.result():
                    m = merchants.setdefault(card["slug"], {
                        "slug": card["slug"],
                        "url": f"{BASE}/{card['slug']}/",
                        "name": card["name"],
                        "cashback": card["cashback"],
                        "upsized": card["upsized"],
                        "categories": [],
                        "tiers": [],
                    })
                    m["upsized"] = m["upsized"] or card["upsized"]
                    cat_name = pretty_category(cat)
                    if cat_name not in m["categories"]:
                        m["categories"].append(cat_name)
            except Exception as e:  # noqa: BLE001 - record and continue
                errors.append({"category": cat, "error": str(e)})
            print(f"  {done}/{len(cat_slugs)} categories scraped", flush=True)

    results = sorted(merchants.values(), key=lambda r: r["name"].lower())
    return results, errors


def write_outputs(results, errors):
    OUT_DIR.mkdir(exist_ok=True)
    payload = {
        "scrapedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "merchantCount": len(results),
        "upsizedCount": sum(1 for r in results if r["upsized"]),
        "errors": errors,
        "merchants": results,
    }
    json_path = OUT_DIR / "topcashback_deals.json"
    json_path.write_text(json.dumps(payload, indent=1, ensure_ascii=False))

    csv_path = OUT_DIR / "topcashback_deals.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["brand", "categories", "cashback", "tier_rates", "upsized", "url"])
        for r in results:
            tiers = "; ".join(
                f"{t['label']}: {t['rate']}" for t in r.get("tiers", [])
            )
            w.writerow(
                [r["name"], "; ".join(r["categories"]), r["cashback"], tiers,
                 "yes" if r["upsized"] else "", r["url"]]
            )
    return payload, json_path, csv_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-enrich", action="store_true",
                    help="skip per-merchant tier enrichment")
    ap.add_argument("--enrich-workers", type=int, default=2,
                    help="parallel workers for merchant page fetches")
    ap.add_argument("--enrich-delay", type=float, default=0.8,
                    help="minimum seconds between merchant page requests")
    ap.add_argument("--enrich-limit", type=int, default=0,
                    help="only enrich the first N 'Up to' merchants (0 = all)")
    ap.add_argument("--no-canvas", action="store_true", help="skip dashboard update")
    args = ap.parse_args()

    print("Fetching category list from sitemap...")
    cats = get_category_slugs()
    print(f"  {len(cats)} categories found")

    print(f"Scraping category listings ({args.workers} parallel)...")
    results, errors = scrape_all(cats, workers=args.workers)

    if not args.no_enrich:
        blocked = enrich_merchants(
            results,
            workers=args.enrich_workers,
            delay=args.enrich_delay,
            limit=args.enrich_limit or None,
        )
        if blocked:
            print(f"  {blocked} merchants had no tier card (blocked or flat rate)")

    payload, json_path, csv_path = write_outputs(results, errors)
    print(f"\nDone: {payload['merchantCount']} merchants "
          f"({payload['upsizedCount']} upsized), {len(errors)} errors")
    print(f"  {json_path}\n  {csv_path}")

    if not args.no_canvas:
        from update_dashboard import update_dashboard

        update_dashboard()

    if errors:
        print("\nFailed categories:")
        for e in errors:
            print(f"  {e['category']}: {e['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
