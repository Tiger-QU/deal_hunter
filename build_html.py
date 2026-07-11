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

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Deal Hunter</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --cream: #FAF7F1;
      --sand: #EDE6D8;
      --ink: #2B2E33;
      --slate: #56636D;
      --slate-light: #8B96A0;
      --green: #2FAE64;
      --green-light: #E3F4E9;
      --coral: #FF5A3C;
      --coral-light: #FFEBE6;
      --font-display: "Fraunces", Georgia, serif;
      --font-ui: "Inter", system-ui, sans-serif;
      --radius: 10px;
      --ease: cubic-bezier(0.22, 1, 0.36, 1);
    }

    *, *::before, *::after { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; }
    body {
      margin: 0;
      font-family: var(--font-ui);
      font-size: 15px;
      line-height: 1.5;
      color: var(--slate);
      background: var(--cream);
    }

    .page {
      max-width: 720px;
      margin: 0 auto;
      padding: 20px 16px 48px;
    }

    /* —— header —— */
    .topbar {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--sand);
      margin-bottom: 28px;
    }
    .logo {
      font-family: var(--font-display);
      font-size: 1.05rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      color: var(--ink);
    }
    .updated {
      font-size: 0.72rem;
      color: var(--slate-light);
      white-space: nowrap;
    }

    /* —— hero —— */
    .hero {
      position: relative;
      margin-bottom: 28px;
    }
    .hero-glow {
      position: absolute;
      top: -20px;
      left: -10%;
      width: 70%;
      height: 120px;
      background: radial-gradient(ellipse, rgba(47, 174, 100, 0.14) 0%, transparent 70%);
      pointer-events: none;
      animation: glow-in 1.2s var(--ease) both;
    }
    @keyframes glow-in {
      from { opacity: 0; transform: scale(0.9); }
      to { opacity: 1; transform: scale(1); }
    }
    .hero h1 {
      position: relative;
      margin: 0 0 10px;
      font-family: var(--font-display);
      font-size: clamp(1.55rem, 5vw, 2rem);
      font-weight: 600;
      line-height: 1.15;
      color: var(--ink);
      letter-spacing: -0.01em;
    }
    .hero-desc {
      position: relative;
      margin: 0;
      font-size: 0.92rem;
      line-height: 1.6;
      color: var(--slate);
      max-width: 36em;
    }

    /* —— controls —— */
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 20px;
    }
    .search-wrap { flex: 1 1 100%; }
    input[type=search], select {
      font: inherit;
      font-size: 0.88rem;
      color: var(--ink);
      background: transparent;
      border: 1px solid var(--sand);
      border-radius: var(--radius);
      padding: 10px 12px;
      width: 100%;
      transition: border-color 0.2s;
    }
    input[type=search]::placeholder { color: var(--slate-light); }
    input[type=search]:focus, select:focus {
      outline: none;
      border-color: var(--green);
    }
    select { flex: 1; min-width: 130px; cursor: pointer; }
    .pills { display: flex; gap: 6px; }
    .pill {
      font: inherit;
      font-size: 0.82rem;
      font-weight: 500;
      padding: 8px 14px;
      border: 1px solid var(--sand);
      border-radius: 999px;
      background: transparent;
      color: var(--slate);
      cursor: pointer;
      transition: background 0.2s, color 0.2s, border-color 0.2s;
    }
    .pill:hover { border-color: var(--ink); color: var(--ink); }
    .pill.active {
      background: var(--ink);
      border-color: var(--ink);
      color: var(--cream);
    }

    /* —— deals section —— */
    .section-label {
      font-family: var(--font-display);
      font-size: 0.78rem;
      font-weight: 500;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--slate-light);
      margin: 0 0 12px;
    }
    .deals { display: flex; flex-direction: column; gap: 0; }

    .brand-group {
      border-top: 1px solid var(--sand);
      padding: 14px 0;
      animation: row-in 0.35s var(--ease) both;
    }
    @keyframes row-in {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @media (prefers-reduced-motion: reduce) {
      .hero-glow, .brand-group { animation: none; }
    }

    .brand-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      min-width: 0;
    }
    .brand-name {
      font-family: var(--font-display);
      font-size: 1.05rem;
      font-weight: 600;
      color: var(--ink);
      text-decoration: none;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .brand-name:hover { text-decoration: underline; }
    .brand-cat {
      font-size: 0.72rem;
      color: var(--slate-light);
      flex-shrink: 0;
      max-width: 42%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      text-align: right;
    }

    .offer {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, max-content);
      grid-template-areas:
        "provider rate"
        "meta meta";
      gap: 6px 10px;
      padding: 10px 12px;
      margin-bottom: 6px;
      border-radius: var(--radius);
      border: 1px solid transparent;
      text-decoration: none;
      color: inherit;
      transition: border-color 0.2s, background 0.2s;
      overflow: hidden;
      min-width: 0;
    }
    .offer:last-child { margin-bottom: 0; }
    .offer:hover { border-color: var(--sand); background: rgba(255,255,255,0.45); }
    .offer.winner {
      border-color: var(--green-light);
      background: var(--green-light);
      border-left: 3px solid var(--green);
    }

    .offer-provider {
      grid-area: provider;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--ink);
      min-width: 0;
    }
    .offer-rate {
      grid-area: rate;
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--ink);
      text-align: right;
      align-self: start;
      min-width: 0;
      max-width: 11em;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .offer-meta {
      grid-area: meta;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      min-width: 0;
      width: 100%;
    }
    .tag {
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      padding: 3px 8px;
      border-radius: 999px;
      flex-shrink: 0;
    }
    .tag-trust { background: var(--green-light); color: var(--green); }
    .tag-urgent { background: var(--coral-light); color: var(--coral); }
    .offer-note {
      flex: 1 1 100%;
      font-size: 0.72rem;
      color: var(--slate-light);
      line-height: 1.4;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }
    .offer-tiers {
      display: flex;
      flex-direction: column;
      gap: 3px;
      width: 100%;
      min-width: 0;
    }
    .tier-row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 0.72rem;
      color: var(--slate-light);
      min-width: 0;
    }
    .tier-label {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
    }
    .tier-rate {
      flex-shrink: 0;
      font-weight: 600;
      color: var(--slate);
      white-space: nowrap;
    }
    .tier-more {
      font-size: 0.68rem;
      color: var(--slate-light);
    }

    @media (max-width: 380px) {
      .offer {
        grid-template-columns: 1fr;
        grid-template-areas:
          "provider"
          "rate"
          "meta";
      }
      .offer-rate {
        max-width: none;
        text-align: left;
      }
    }

    .empty {
      padding: 40px 16px;
      text-align: center;
      color: var(--slate-light);
      font-size: 0.9rem;
      border-top: 1px solid var(--sand);
    }
    .foot {
      margin-top: 20px;
      font-size: 0.75rem;
      color: var(--slate-light);
      line-height: 1.5;
    }
  </style>
</head>
<body>
  <div class="page">
    <header class="topbar">
      <span class="logo">Deal Hunter</span>
      <span class="updated" id="updated"></span>
    </header>

    <section class="hero">
      <div class="hero-glow" aria-hidden="true"></div>
      <h1>Know before you buy.</h1>
      <p class="hero-desc">
        Compare cashback rates from ShopBack and TopCashback in one place.
        Search a store before you shop — see which site pays more, what's upsized,
        and open the offer with one tap.
      </p>
    </section>

    <div class="controls">
      <div class="search-wrap">
        <input type="search" id="q" placeholder="Search a brand, e.g. Nike, Agoda, Myer…" autocomplete="off">
      </div>
      <div class="pills">
        <button type="button" class="pill active" id="allBtn">All</button>
        <button type="button" class="pill" id="upBtn">Upsized</button>
      </div>
      <select id="cat"><option value="all">All categories</option></select>
      <select id="sort">
        <option value="rate">Highest rate</option>
        <option value="name">Brand A–Z</option>
      </select>
    </div>

    <p class="section-label">Deals</p>
    <div class="deals" id="deals"></div>
    <p class="foot" id="foot"></p>
  </div>

  <script>
    const DATA = __DATA_JSON__;
    const $ = (id) => document.getElementById(id);

    function maxPct(s) {
      if (!s) return -1;
      const m = s.match(/(\d+(?:\.\d+)?)\s*%/g);
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
    function endsLabel(iso) {
      if (!iso) return null;
      const ms = new Date(iso) - Date.now();
      if (ms <= 0) return "Ended";
      const h = ms / 3600000;
      if (h < 24) return `Ends in ${Math.max(1, Math.round(h))}h`;
      const d = Math.round(h / 24);
      return d === 1 ? "Ends in 1d" : `Ends in ${d}d`;
    }
    function statusTags(o) {
      const tags = [];
      if (o.upsized) tags.push('<span class="tag tag-trust">✓ Upsized</span>');
      const end = endsLabel(o.upsizeEndAt);
      if (end && end !== "Ended") tags.push(`<span class="tag tag-urgent">● ${esc(end)}</span>`);
      return tags.join("");
    }
    function shortLabel(s, max = 48) {
      s = (s || "").replace(/\s+/g, " ").trim();
      return s.length <= max ? s : s.slice(0, max - 1) + "…";
    }
    function tierDetail(o) {
      const tiers = o.tiers || [];
      if (tiers.length) {
        const max = 3;
        const rows = tiers.slice(0, max).map(t =>
          `<span class="tier-row"><span class="tier-label" title="${esc(t.label)}">`
          + `${esc(shortLabel(t.label))}</span>`
          + `<span class="tier-rate">${esc(t.rate)}</span></span>`
        ).join("");
        const more = tiers.length > max
          ? `<span class="tier-more">+${tiers.length - max} more categories</span>` : "";
        return `<div class="offer-tiers">${rows}${more}</div>`;
      }
      return o.note ? `<span class="offer-note">${esc(o.note)}</span>` : "";
    }

    let onlyUp = false;
    const cats = [...new Set(DATA.brands.map(b => b.category))]
      .sort((a, b) => (a === "Other" ? 1 : b === "Other" ? -1 : a.localeCompare(b)));

    function render() {
      const q = $("q").value.trim().toLowerCase();
      const cat = $("cat").value;
      const sort = $("sort").value;
      let list = DATA.brands.filter(b => {
        if (onlyUp && !b.offers.some(o => o.upsized)) return false;
        if (cat !== "all" && b.category !== cat) return false;
        if (!q) return true;
        return b.brand.toLowerCase().includes(q) ||
          b.offers.some(o =>
            (o.note || "").toLowerCase().includes(q) ||
            (o.tiers || []).some(t =>
              (t.label || "").toLowerCase().includes(q) ||
              (t.rate || "").toLowerCase().includes(q)
            )
          );
      });
      if (sort === "rate") {
        list.sort((a, b) =>
          Math.max(...b.offers.map(o => maxPct(o.cashback))) -
          Math.max(...a.offers.map(o => maxPct(o.cashback))));
      } else {
        list.sort((a, b) => a.brand.localeCompare(b.brand));
      }

      const max = 150;
      const shown = list.slice(0, max);
      const root = $("deals");
      root.innerHTML = "";

      if (!shown.length) {
        root.innerHTML = '<p class="empty">No brands match — try a shorter name.</p>';
        $("foot").textContent = "";
        return;
      }

      shown.forEach((b, gi) => {
        const win = winnerIdx(b.offers);
        const group = document.createElement("div");
        group.className = "brand-group";
        group.style.animationDelay = `${Math.min(gi, 12) * 30}ms`;

        const head = document.createElement("div");
        head.className = "brand-head";
        head.innerHTML = `
          <a class="brand-name" href="${esc(b.offers[0].url)}">${esc(b.brand)}</a>
          <span class="brand-cat">${esc(b.category)}</span>`;
        group.appendChild(head);

        b.offers.forEach((o, i) => {
          const a = document.createElement("a");
          a.className = "offer" + (i === win ? " winner" : "");
          a.href = o.url;
          a.target = "_blank";
          a.rel = "noopener";
          const note = tierDetail(o);
          a.innerHTML = `
            <span class="offer-provider">${esc(o.provider)}</span>
            <span class="offer-rate">${esc(o.cashback || "—")}</span>
            <div class="offer-meta">${statusTags(o)}${note}</div>`;
          group.appendChild(a);
        });
        root.appendChild(group);
      });

      $("foot").textContent = list.length > max
        ? `Showing ${max} of ${list.length} brands — narrow your search. Green highlight = higher rate when both sites list the brand.`
        : "Green highlight = higher rate when both sites list the brand.";
    }

    const when = DATA.scrapedAt
      ? new Date(DATA.scrapedAt).toLocaleString("en-AU", { dateStyle: "medium", timeStyle: "short" })
      : "";
    $("updated").textContent = when ? `Updated ${when}` : "";

    for (const c of cats) {
      const o = document.createElement("option");
      o.value = c;
      o.textContent = c;
      $("cat").appendChild(o);
    }

    $("q").oninput = render;
    $("cat").onchange = render;
    $("sort").onchange = render;
    $("allBtn").onclick = () => {
      onlyUp = false;
      $("allBtn").classList.add("active");
      $("upBtn").classList.remove("active");
      render();
    };
    $("upBtn").onclick = () => {
      onlyUp = true;
      $("upBtn").classList.add("active");
      $("allBtn").classList.remove("active");
      render();
    };
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
