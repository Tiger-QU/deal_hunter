"""HTTP fetching helpers shared by the scrapers.

Uses cloudscraper when installed (needed for ShopBack/Cloudflare from
GitHub Actions). Falls back to urllib with cookies and browser-like headers.
"""

from __future__ import annotations

import http.cookiejar
import time
import urllib.error
import urllib.request

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

_cookie_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookie_jar))
_warmed_hosts: set[str] = set()
_cloudscraper = None
_cloudscraper_checked = False


def _cloudscraper_session():
    global _cloudscraper, _cloudscraper_checked
    if _cloudscraper_checked:
        return _cloudscraper
    _cloudscraper_checked = True
    try:
        import cloudscraper

        _cloudscraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "linux", "desktop": True}
        )
    except ImportError:
        _cloudscraper = None
    return _cloudscraper


def warmup(base_url: str) -> None:
    """Prime cookies against a site's homepage (helps Cloudflare)."""
    host = base_url.rstrip("/")
    if host in _warmed_hosts:
        return
    try:
        fetch(host + "/", referer=host + "/")
    except Exception:
        pass
    _warmed_hosts.add(host)


def fetch(url, timeout=30, retries=4, referer=None, backoff=2.0):
    """Fetch a URL; prefer cloudscraper, else cookie-aware urllib."""
    last_err = None
    headers = dict(BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "same-origin"

    scraper = _cloudscraper_session()
    if scraper is not None:
        for attempt in range(retries):
            try:
                resp = scraper.get(url, headers=headers, timeout=timeout)
                if resp.status_code == 403:
                    raise urllib.error.HTTPError(
                        url, 403, "Forbidden", resp.headers, None
                    )
                resp.raise_for_status()
                return resp.text
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(backoff * (attempt + 1))
        raise RuntimeError(f"failed to fetch {url}: {last_err}")

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with _opener.open(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_err}")
