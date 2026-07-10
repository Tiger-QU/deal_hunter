#!/usr/bin/env python3
"""Build a static phone-friendly dashboard at docs/index.html.

Reads the scraped JSON in data/ (via update_dashboard.build_combined) and
writes a single HTML file suitable for GitHub Pages.
"""

import json
from pathlib import Path

from update_dashboard import build_combined

DOCS_DIR = Path(__file__).resolve().parent / "docs"
OUT = DOCS_DIR / "index.html"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Deal Hunter</title>
  <style>
    :root { font-family: system-ui, -apple-system, sans-serif; color: #111; background: #f6f6f6; }
    body { margin: 0; padding: 16px; max-width: 960px; margin-inline: auto; }
    h1 { font-size: 1.35rem; margin: 0 0 4px; }
    .meta { color: #555; font-size: 0.85rem; margin-bottom: 16px; }
    .stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 16px; }
    @media (min-width: 600px) { .stats { grid-template-columns: repeat(4, 1fr); } }
    .stat { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 10px 12px; }
    .stat b { display: block; font-size: 1.2rem; }
    .stat span { font-size: 0.75rem; color: #555; }
    .controls { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    input, select, button {
      font: inherit; padding: 8px 10px; border: 1px solid #ccc; border-radius: 6px; background: #fff;
    }
    input[type=search] { flex: 1; min-width: 180px; }
    button.active { background: #111; color: #fff; border-color: #111; }
    table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd; }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; vertical-align: top; }
    th { background: #fafafa; font-size: 0.8rem; position: sticky; top: 0; }
    tr.winner td { background: #eefbf0; }
    tr.brand-start td { border-top: 2px solid #ddd; }
    .upsized { color: #0a5; font-weight: 600; font-size: 0.85rem; }
    .std { color: #999; font-size: 0.85rem; }
    .note { color: #666; font-size: 0.8rem; }
    a { color: inherit; }
    .empty { padding: 24px; text-align: center; color: #666; }
  </style>
</head>
<body>
  <h1>Deal Hunter — ShopBack vs TopCashback</h1>
  <p class="meta" id="meta"></p>
  <div class="stats" id="stats"></div>
  <div class="controls">
    <input type="search" id="q" placeholder="Search brand, e.g. nike, agoda…">
    <button type="button" id="allBtn" class="active">All</button>
    <button type="button" id="upBtn">Upsized only</button>
    <select id="cat"><option value="all">All categories</option></select>
    <select id="sort">
      <option value="rate">Highest rate</option>
      <option value="name">Brand A–Z</option>
    </select>
  </div>
  <table>
    <thead><tr><th>Brand</th><th>Site</th><th>Cashback</th><th>Status</th><th>Notes</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <p class="meta" id="foot"></p>
  <script>
    const DATA = __DATA_JSON__;
    const $ = (id) => document.getElementById(id);

    function maxPct(s) {
      if (!s) return -1;
      const m = s.match(/(\\d+(?:\\.\\d+)?)\\s*%/g);
      return m ? Math.max(...m.map(x => parseFloat(x))) : -0.5;
    }
    function winnerIdx(offers) {
      if (offers.length < 2) return -1;
      const r = offers.map(o => maxPct(o.cashback));
      if (r.some(x => x <= 0)) return -1;
      const mx = Math.max(...r);
      return r.filter(x => x === mx).length === 1 ? r.indexOf(mx) : -1;
    }
    function esc(s) {
      return (s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");
    }

    let onlyUp = false;
    const cats = [...new Set(DATA.brands.map(b => b.category))].sort();

    function render() {
      const q = $("q").value.trim().toLowerCase();
      const cat = $("cat").value;
      const sort = $("sort").value;
      let list = DATA.brands.filter(b => {
        if (onlyUp && !b.offers.some(o => o.upsized)) return false;
        if (cat !== "all" && b.category !== cat) return false;
        if (!q) return true;
        return b.brand.toLowerCase().includes(q) ||
          b.offers.some(o => (o.note || "").toLowerCase().includes(q));
      });
      if (sort === "rate") {
        list.sort((a, b) => Math.max(...b.offers.map(o => maxPct(o.cashback))) -
                           Math.max(...a.offers.map(o => maxPct(o.cashback))));
      } else {
        list.sort((a, b) => a.brand.localeCompare(b.brand));
      }
      const max = 150;
      const shown = list.slice(0, max);
      const tbody = $("rows");
      tbody.innerHTML = "";
      if (!shown.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No matches</td></tr>';
        return;
      }
      for (const b of shown) {
        const win = winnerIdx(b.offers);
        b.offers.forEach((o, i) => {
          const tr = document.createElement("tr");
          if (i === 0) tr.classList.add("brand-start");
          if (i === win) tr.classList.add("winner");
          tr.innerHTML = `
            <td>${i === 0 ? `<a href="${esc(o.url)}"><b>${esc(b.brand)}</b></a>` : ""}</td>
            <td><a href="${esc(o.url)}">${esc(o.provider)}</a></td>
            <td>${esc(o.cashback || "—")}</td>
            <td class="${o.upsized ? "upsized" : "std"}">${o.upsized ? "Upsized" : "standard"}</td>
            <td class="note">${esc(o.note || "")}</td>`;
          tbody.appendChild(tr);
        });
      }
      $("foot").textContent = list.length > max
        ? `Showing ${max} of ${list.length} brands — narrow your search.`
        : "";
    }

    const both = DATA.brands.filter(b => b.offers.length > 1).length;
    const ups = DATA.brands.filter(b => b.offers.some(o => o.upsized)).length;
    const when = DATA.scrapedAt ? new Date(DATA.scrapedAt).toLocaleString("en-AU") : "unknown";
    $("meta").textContent = "Updated " + when + ". Green row = better rate when brand is on both sites.";
    $("stats").innerHTML = `
      <div class="stat"><b>${DATA.brands.length}</b><span>Brands</span></div>
      <div class="stat"><b>${both}</b><span>On both sites</span></div>
      <div class="stat"><b>${ups}</b><span>Upsized</span></div>
      <div class="stat"><b>2</b><span>Sources</span></div>`;
    for (const c of cats) {
      const o = document.createElement("option");
      o.value = c; o.textContent = c;
      $("cat").appendChild(o);
    }
    $("q").oninput = render;
    $("cat").onchange = render;
    $("sort").onchange = render;
    $("allBtn").onclick = () => { onlyUp = false; $("allBtn").classList.add("active"); $("upBtn").classList.remove("active"); render(); };
    $("upBtn").onclick = () => { onlyUp = true; $("upBtn").classList.add("active"); $("allBtn").classList.remove("active"); render(); };
    render();
  </script>
</body>
</html>
"""


def main():
    data = build_combined()
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / ".nojekyll").touch()
    payload = json.dumps(data, ensure_ascii=False)
    OUT.write_text(HTML_TEMPLATE.replace("__DATA_JSON__", payload), encoding="utf-8")
    both = sum(1 for b in data["brands"] if len(b["offers"]) > 1)
    print(f"built {OUT} — {len(data['brands'])} brands ({both} on both providers)")


if __name__ == "__main__":
    main()
