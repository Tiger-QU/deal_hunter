#!/usr/bin/env python3
"""Rebuild the combined deal-hunter dashboard canvas.

Reads data/shopback_deals.json and data/topcashback_deals.json (whichever
exist), matches brands across the two providers by normalised name/slug, and
injects the combined dataset into the canvas between the DATA_START/DATA_END
markers. Run directly, or let the scrapers call it after a refresh:

  python3 update_dashboard.py
"""

import json
import re
from pathlib import Path

from tier_utils import display_tiers, format_tier_note

OUT_DIR = Path(__file__).resolve().parent / "data"
CANVAS_PATH = Path(
    "/Users/Tiger/.cursor/projects/Users-Tiger-Documents-PJ-Shopback/canvases/"
    "shopback-deals.canvas.tsx"
)

STOPWORDS = {"australia", "au", "the", "online", "store", "official"}

# TopCashback's fine-grained categories -> the dashboard's coarse groups
# (same taxonomy as the ShopBack scraper). Used as a fallback for brands
# that aren't on ShopBack.
TCB_CATEGORY_MAP = {
    "Accessories": "Fashion", "Accommodation": "Travel",
    "Activewear": "Fashion", "Alcohol": "Alcohol",
    "Apps and Services": "Digital & VPNs", "Body and Hair": "Beauty",
    "Books Magazines": "Books & Media", "Car Hire": "Cars & Auto",
    "Cars and Bikes": "Cars & Auto", "Cosmetics": "Beauty",
    "Diy": "Home & Garden", "Electricals": "Tech",
    "Energy": "Finance & Utilities", "Experiences": "Activities",
    "Eyecare": "Health & Beauty", "Fashion": "Fashion",
    "Flights": "Travel", "Food": "Food Delivery",
    "Food and Drinks": "Grocery", "Footwear": "Fashion",
    "Fragrances": "Beauty", "Furniture": "Home & Garden",
    "Garden": "Home & Garden", "Gifts": "Home & Garden",
    "Health and Beauty": "Health & Beauty", "Holidays": "Travel",
    "Home Appliances": "Home & Garden", "Home and Garden": "Home & Garden",
    "Insurance": "Finance & Utilities", "Interior Decor": "Home & Garden",
    "Iphone": "Tech", "Jewellery": "Fashion",
    "Kidswear": "Baby & Kids", "Laptops and Computers": "Tech",
    "Lingerie": "Fashion", "Luxury": "Fashion",
    "Marketplace": "Marketplace", "Menswear": "Fashion",
    "Mobile Accessories": "Tech", "Mobile Phones": "Tech",
    "Nutrition and Supplements": "Health & Beauty",
    "Office Equipment": "Tech", "Outdoorwear": "Fashion",
    "Parent Baby Toddler": "Baby & Kids", "Pets": "Pets",
    "Pharmacy": "Health & Beauty", "Property": "Finance & Utilities",
    "Sim Only and Mobile Plans": "Digital & VPNs",
    "Sports and Outdoors": "Fitness & Sports",
    "Stationery": "Books & Media", "Toys and Games": "Toys & Gaming",
    "Travel": "Travel", "Utilities": "Finance & Utilities",
    "Vpn and Software": "Digital & VPNs", "Womenswear": "Fashion",
}


def tcb_category(categories):
    for c in categories or []:
        mapped = TCB_CATEGORY_MAP.get(c)
        if mapped:
            return mapped
    return None


def norm_key(name, slug=""):
    """Normalise a brand name for cross-provider matching."""
    s = name.lower()
    s = s.replace("&amp;", "&").replace("&", "and").replace("+", "plus")
    s = re.sub(r"\(.*?\)", " ", s)          # drop "(Compare)" etc.
    s = re.sub(r"[^a-z0-9]+", " ", s)
    words = [w for w in s.split() if w not in STOPWORDS]
    key = "".join(words)
    if not key:  # name was all stopwords; fall back to the slug
        key = re.sub(r"[^a-z0-9]", "", slug.lower())
    return key


def load(path):
    p = OUT_DIR / path
    return json.load(open(p)) if p.exists() else None


def build_combined():
    sb = load("shopback_deals.json")
    tcb = load("topcashback_deals.json")

    brands = {}

    def entry(key, name):
        if key not in brands:
            brands[key] = {"brand": name, "category": None, "offers": []}
        return brands[key]

    for s in (sb or {}).get("stores", []):
        key = norm_key(s["name"], s["slug"])
        b = entry(key, s["name"])
        b["category"] = s.get("category") or b["category"]
        tiers = display_tiers(s.get("tiers"))
        b["offers"].append({
            "provider": "ShopBack",
            "cashback": s["cashback"],
            "upsized": s["upsized"],
            "upsizeEndAt": s["upsizeEndAt"],
            "tiers": tiers,
            "note": format_tier_note(tiers),
            "url": s["url"],
        })

    for m in (tcb or {}).get("merchants", []):
        key = norm_key(m["name"], m["slug"])
        b = entry(key, m["name"])
        if not b["category"]:
            b["category"] = tcb_category(m.get("categories"))
        tiers = display_tiers(m.get("tiers"))
        cat_fallback = "; ".join(m.get("categories", [])[:3]) or None
        b["offers"].append({
            "provider": "TopCashback",
            "cashback": m["cashback"],
            "upsized": m["upsized"],
            "upsizeEndAt": None,
            "tiers": tiers,
            "note": format_tier_note(tiers, fallback=cat_fallback),
            "url": m["url"],
        })

    combined = sorted(brands.values(), key=lambda b: b["brand"].lower())
    for b in combined:
        b["category"] = b["category"] or "Other"
        b["offers"].sort(key=lambda o: o["provider"])

    scraped = max(
        filter(None, [(sb or {}).get("scrapedAt"), (tcb or {}).get("scrapedAt")]),
        default="",
    )
    return {"scrapedAt": scraped, "brands": combined}


def update_dashboard():
    data = build_combined()
    if not CANVAS_PATH.exists():
        print(f"canvas not found at {CANVAS_PATH}, skipping")
        return
    src = CANVAS_PATH.read_text()
    data_js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    new_src = re.sub(
        r"/\* DATA_START \*/.*?/\* DATA_END \*/",
        "/* DATA_START */ " + data_js + " /* DATA_END */",
        src,
        flags=re.S,
    )
    CANVAS_PATH.write_text(new_src)
    both = sum(1 for b in data["brands"] if len(b["offers"]) > 1)
    print(f"canvas updated: {len(data['brands'])} brands "
          f"({both} on both providers)")


if __name__ == "__main__":
    update_dashboard()
