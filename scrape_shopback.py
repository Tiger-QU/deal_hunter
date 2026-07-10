#!/usr/bin/env python3
"""Scrape ShopBack Australia cashback deals for all stores.

Data sources (no login, plain HTTP):
  1. https://www.shopback.com.au/sitemap.xml  -> list of all store page URLs
  2. Each store page HTML embeds a Next.js RSC payload containing the live
     offer JSON: display rate, upsize flag, upsize end time, per-category tiers.

Outputs:
  data/shopback_deals.json   full structured data
  data/shopback_deals.csv    flat spreadsheet-friendly version
  (optional) injects the data into the dashboard canvas so it shows fresh deals

Usage:
  python3 scrape_shopback.py                 # full run (~1,400 stores, a few minutes)
  python3 scrape_shopback.py --limit 30      # quick test run
  python3 scrape_shopback.py --no-canvas     # skip canvas injection
"""

import argparse
import collections
import concurrent.futures
import csv
import datetime
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://www.shopback.com.au"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-AU,en;q=0.9",
}
OUT_DIR = Path(__file__).resolve().parent / "data"

# Pages in the sitemap that are not store pages.
NON_STORE_SLUGS = {
    "travels", "upsizes", "all-stores", "all--stores", "vouchers",
    "online-cashback-how-it-works", "shopback-plus", "fashion-promo",
    "home-living", "travel", "referral-program", "gift-cards", "blog",
    "guide", "tech-and-gadgets",
    # category hub pages, not stores
    "alcohol", "beauty", "compare", "digital-goods", "finance", "fitness",
    "food-delivery", "groceries", "health-personal-care", "kids",
    "marketplace", "pet", "survey", "westpac",
}

# ShopBack's "universalCategories" primary-category ID -> display name.
# Built by cross-referencing each store's ID with the l1_category_name that
# appears in its "similar stores" widget, then hand-checked against sample
# store names (a few IDs get a clearer label than ShopBack's own, e.g. 28 is
# all pet stores but ShopBack labels them "Home & Garden").
# resolve_categories() falls back to the page's own label for unknown IDs
# and reports them so this map can be extended.
UNIVERSAL_CATEGORY_NAMES = {
    2: "Beauty",
    3: "Beauty",
    4: "Tech",
    5: "Fashion",
    6: "Activities",
    7: "Fitness & Sports",
    8: "Food Delivery",
    9: "Food Delivery",
    10: "Marketplace",
    11: "Grocery",
    12: "Alcohol",
    13: "Health & Beauty",
    14: "Home & Garden",
    15: "Home & Garden",
    16: "Baby & Kids",
    17: "Finance & Utilities",
    18: "Finance & Utilities",
    19: "Finance & Utilities",
    20: "Digital & VPNs",
    21: "Toys & Gaming",
    22: "Digital & VPNs",
    23: "Digital & VPNs",
    24: "Travel",
    25: "Cars & Auto",
    27: "Books & Media",
    28: "Pets",
    29: "Finance & Utilities",
}


def resolve_categories(results):
    """Give every store a final category name.

    The curated ID map wins; stores whose ID is unknown keep the label voted
    from their own page. Returns the set of IDs that had no curated name.
    """
    unknown = collections.defaultdict(collections.Counter)
    for r in results:
        curated = UNIVERSAL_CATEGORY_NAMES.get(r["categoryId"])
        if curated:
            r["category"] = curated
        elif r["categoryId"] is not None:
            unknown[r["categoryId"]][r["category"] or "?"] += 1
        if not r["category"]:
            r["category"] = "Other"
    return unknown


def fetch(url, timeout=30, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001 - retry any network error
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_err}")


def get_store_slugs():
    xml = fetch(BASE + "/sitemap.xml")
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    slugs = []
    for loc in locs:
        path = loc.replace(BASE, "").strip("/")
        # store pages are exactly one path segment, e.g. /agoda
        if path and "/" not in path and path not in NON_STORE_SLUGS:
            slugs.append(path)
    return sorted(set(slugs))


def decode_rsc_payload(html):
    """Join and unescape all self.__next_f.push([1,"..."]) string chunks."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    out = []
    for c in chunks:
        try:
            out.append(json.loads('"' + c + '"'))
        except json.JSONDecodeError:
            pass
    return "".join(out)


def extract_balanced(text, start):
    """Extract a balanced {...} JSON object starting at text[start] == '{'."""
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None


def parse_store(slug, html):
    blob = decode_rsc_payload(html)

    name = None
    m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
    if m:
        name = m.group(1).strip()

    record = {
        "slug": slug,
        "url": f"{BASE}/{slug}",
        "name": name or slug,
        "cashback": None,
        "upsized": False,
        "upsizeEndAt": None,
        "tiers": [],
        "trackingTime": None,
        "claimTime": None,
        "categoryId": None,
        "category": None,
    }

    m = re.search(r'"universalCategories":\[(\d+)', blob)
    if m:
        record["categoryId"] = int(m.group(1))

    # The "similar stores" widget labels stores in the same vertical with
    # l1/l2 category names; majority vote gives this store's own category.
    l1_votes = collections.Counter(
        v.strip() for v in re.findall(r'"l1_category_name":"([^"]+)"', blob)
    )
    if l1_votes:
        record["category"] = l1_votes.most_common(1)[0][0]

    i = blob.find('"currentOffer":{')
    if i >= 0:
        obj_text = extract_balanced(blob, i + len('"currentOffer":'))
        if obj_text:
            try:
                offer = json.loads(obj_text)
            except json.JSONDecodeError:
                offer = None
            if offer:
                rendered = offer.get("renderedOffer") or {}
                display = rendered.get("displayText")
                if display:
                    # ShopBack's raw data doubles the dollar sign ("$$288")
                    display = display.replace("$$", "$")
                record["cashback"] = display
                offer_types = offer.get("offerTypes") or [offer.get("offerType")]
                record["upsized"] = "UPSIZE" in offer_types
                if record["upsized"]:
                    record["upsizeEndAt"] = offer.get("endAt")
                for tier in offer.get("cashbackTiers") or []:
                    label = tier.get("label")
                    disp = tier.get("displayText")
                    if label and disp:
                        record["tiers"].append({"label": label, "rate": disp})

    # fallback: title tag, e.g. "Agoda | < 13% Cashback, Discount Codes ..."
    if not record["cashback"]:
        m = re.search(r"<title>[^|<]*\|\s*([^,<]*Cashback)", html)
        if m:
            record["cashback"] = (
                m.group(1).replace("&lt;", "Up to").replace("&amp;", "&").strip()
            )

    m = re.search(r'"displayTrackingTime":"([^"]+)"', blob)
    if m:
        record["trackingTime"] = m.group(1)
    m = re.search(r'"displayClaimTime":"([^"]+)"', blob)
    if m:
        record["claimTime"] = m.group(1)

    return record


def scrape_all(slugs, workers=16):
    results = []
    errors = []

    def work(slug):
        html = fetch(f"{BASE}/{slug}")
        return parse_store(slug, html)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, s): s for s in slugs}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            slug = futures[fut]
            done += 1
            try:
                results.append(fut.result())
            except Exception as e:  # noqa: BLE001 - record and continue
                errors.append({"slug": slug, "error": str(e)})
            if done % 100 == 0 or done == len(slugs):
                print(f"  {done}/{len(slugs)} pages fetched", flush=True)

    results.sort(key=lambda r: r["name"].lower())
    return results, errors


def write_outputs(results, errors):
    OUT_DIR.mkdir(exist_ok=True)
    payload = {
        "scrapedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "storeCount": len(results),
        "upsizedCount": sum(1 for r in results if r["upsized"]),
        "errors": errors,
        "stores": results,
    }
    json_path = OUT_DIR / "shopback_deals.json"
    json_path.write_text(json.dumps(payload, indent=1, ensure_ascii=False))

    csv_path = OUT_DIR / "shopback_deals.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["brand", "category", "cashback", "upsized", "upsize_ends_at_utc",
             "category_rates", "tracking_time", "claim_time", "url"]
        )
        for r in results:
            tiers = "; ".join(f"{t['label']}: {t['rate']}" for t in r["tiers"])
            w.writerow(
                [r["name"], r["category"] or "", r["cashback"] or "",
                 "yes" if r["upsized"] else "", r["upsizeEndAt"] or "", tiers,
                 r["trackingTime"] or "", r["claimTime"] or "", r["url"]]
            )
    return payload, json_path, csv_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only scrape first N stores (testing)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--no-canvas", action="store_true", help="skip canvas injection")
    args = ap.parse_args()

    print("Fetching store list from sitemap...")
    slugs = get_store_slugs()
    print(f"  {len(slugs)} store pages found")
    if args.limit:
        slugs = slugs[: args.limit]

    print(f"Scraping {len(slugs)} store pages ({args.workers} parallel)...")
    results, errors = scrape_all(slugs, workers=args.workers)

    unknown_ids = resolve_categories(results)
    if unknown_ids:
        print("\nCategory IDs missing from UNIVERSAL_CATEGORY_NAMES "
              "(using page labels as fallback):")
        for cat_id, votes in sorted(unknown_ids.items()):
            print(f"  {cat_id}: {dict(votes.most_common(3))}")

    payload, json_path, csv_path = write_outputs(results, errors)
    print(f"\nDone: {payload['storeCount']} stores "
          f"({payload['upsizedCount']} upsized), {len(errors)} errors")
    print(f"  {json_path}\n  {csv_path}")

    if not args.no_canvas:
        from update_dashboard import update_dashboard

        update_dashboard()

    if errors:
        print("\nFailed slugs:")
        for e in errors[:20]:
            print(f"  {e['slug']}: {e['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
