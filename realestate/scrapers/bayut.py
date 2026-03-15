"""
Bayut.com scraper
=================
Bayut uses aggressive bot protection (EMPG hb-challenge + captcha).
Plain HTTP and headless browsers get blocked.

Strategy (ordered by preference):
  1. Cookie-based HTTP — if valid cookies exist (from a prior browser session),
     use plain requests with those cookies.  Fastest and most reliable.
  2. Playwright with manual captcha solve — launch a visible browser, let the
     user solve the captcha once, then save cookies for future runs.
  3. If all else fails, skip Bayut and rely on PropertyFinder.

Cookie management:
  - Cookies are saved to data/bayut_cookies.json
  - They typically last 24–72 hours
  - Call `refresh_bayut_cookies()` interactively to re-solve the captcha

Public interface:
  fetch_bayut_listings(purpose, locations) → list[dict]
  refresh_bayut_cookies() → bool  (interactive, requires display)
"""

import json
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import (
    BAYUT,
    BUDGET_PROFILES,
    HEADERS,
    MAX_PAGES_PER_SEARCH,
    PROJECT_ROOT,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
)
from utils.logger import get_logger

log = get_logger()

COOKIE_FILE = PROJECT_ROOT / "data" / "bayut_cookies.json"


# ─── Cookie management ──────────────────────────────────────────────

def _load_cookies() -> dict:
    """Load saved cookies from file."""
    if COOKIE_FILE.exists():
        try:
            with open(COOKIE_FILE) as f:
                cookies = json.load(f)
            log.debug("Loaded %d Bayut cookies from file", len(cookies))
            return cookies
        except (json.JSONDecodeError, IOError) as exc:
            log.warning("Failed to load Bayut cookies: %s", exc)
    return {}


def _save_cookies(cookies: dict):
    """Persist cookies to file."""
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f, indent=2)
    log.info("Saved %d Bayut cookies to %s", len(cookies), COOKIE_FILE)


def refresh_bayut_cookies() -> bool:
    """
    Launch a visible Playwright browser, navigate to Bayut, wait for the user
    to solve the captcha, then save cookies.  Returns True on success.
    
    For headless/server environments, you can also manually export cookies
    from your browser and save them to data/bayut_cookies.json in the format:
    {"cookie_name": "cookie_value", ...}
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    log.info("Launching browser for Bayut cookie refresh (solve the captcha manually)...")

    with sync_playwright() as pw:
        # Launch VISIBLE browser so user can solve captcha
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            locale="en-US",
            viewport={"width": 1920, "height": 1080},
        )
        page = ctx.new_page()
        page.goto("https://www.bayut.com/for-sale/property/abu-dhabi/", timeout=60000)

        print("\n" + "=" * 60)
        print("  BAYUT COOKIE REFRESH")
        print("  Solve the captcha in the browser window.")
        print("  Once you see property listings, press ENTER here.")
        print("=" * 60 + "\n")

        input("Press ENTER after solving the captcha...")

        # Extract cookies
        pw_cookies = ctx.cookies()
        cookies = {c["name"]: c["value"] for c in pw_cookies}
        _save_cookies(cookies)

        browser.close()

    return True


# ─── HTTP session with cookies ───────────────────────────────────────

def _get_session() -> requests.Session | None:
    """Create a requests session with Bayut cookies.  Returns None if no cookies."""
    cookies = _load_cookies()
    if not cookies:
        return None

    session = requests.Session()
    session.headers.update(HEADERS)
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".bayut.com")
    return session


# ─── URL builders ────────────────────────────────────────────────────

def _build_url(purpose: str, city: str, slug: str, page: int = 1) -> str:
    tpl = BAYUT["sale_path_tpl"] if purpose == "sale" else BAYUT["rent_path_tpl"]
    path = tpl.format(city=city, slug=slug)
    url = urljoin(BAYUT["base_url"], path)
    if page > 1:
        url += f"?{BAYUT['page_param']}={page}"
    return url


# ─── __NEXT_DATA__ extractor ────────────────────────────────────────

def _extract_next_data(html: str) -> dict | None:
    match = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        log.warning("Failed to parse __NEXT_DATA__: %s", exc)
        return None


def _listings_from_next_data(data: dict) -> list[dict]:
    props = data.get("props", {}).get("pageProps", {})
    for accessor in [
        lambda p: p.get("searchResult", {}).get("hits", []),
        lambda p: p.get("properties", []),
        lambda p: p.get("hits", []),
    ]:
        hits = accessor(props)
        if hits and isinstance(hits, list):
            return hits
    return []


def _page_count_from_next_data(data: dict) -> int:
    props = data.get("props", {}).get("pageProps", {})
    n = props.get("searchResult", {}).get("nbPages") or props.get("nbPages")
    return int(n) if n else 1


# ─── Normaliser ──────────────────────────────────────────────────────

def _normalise(raw: dict, purpose: str, city: str, area_name: str) -> dict | None:
    ext_id = str(raw.get("externalID") or raw.get("id", ""))
    if not ext_id:
        return None

    price = raw.get("price")
    if price is None:
        return None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None

    # Enforce budget profile price limits
    budget = BUDGET_PROFILES.get(purpose)
    if budget:
        if price > budget["max_price"] or price < budget["min_price"]:
            return None

    loc_parts = []
    for loc in raw.get("location", []):
        if isinstance(loc, dict):
            loc_parts.append(loc.get("name", ""))
        elif isinstance(loc, str):
            loc_parts.append(loc)
    location_full = ", ".join([p for p in loc_parts if p])

    geo = raw.get("geography", {}) or {}
    lat = geo.get("lat") or raw.get("latitude")
    lng = geo.get("lng") or raw.get("longitude")

    category = raw.get("category", [])
    if isinstance(category, list) and category:
        ptype = category[-1].get("name", "").lower() if isinstance(category[-1], dict) else ""
    elif isinstance(category, dict):
        ptype = category.get("name", "").lower()
    else:
        ptype = ""

    completion = raw.get("completionStatus", "")
    is_offplan = "off" in str(completion).lower() or "plan" in str(completion).lower()

    slug = raw.get("slug", "")
    url = f"{BAYUT['base_url']}/property/details-{ext_id}.html"
    if slug:
        url = f"{BAYUT['base_url']}/{slug}"

    return {
        "id": f"bayut_{ext_id}",
        "source": "bayut",
        "external_id": ext_id,
        "purpose": purpose,
        "property_type": ptype,
        "title": raw.get("title", ""),
        "price": price,
        "currency": raw.get("currency", "AED"),
        "area_sqft": _safe_float(raw.get("area")),
        "bedrooms": _safe_int(raw.get("rooms") if raw.get("rooms") is not None else raw.get("bedrooms")),
        "bathrooms": _safe_int(raw.get("baths") if raw.get("baths") is not None else raw.get("bathrooms")),
        "city": city,
        "area_name": area_name,
        "location_full": location_full,
        "latitude": _safe_float(lat),
        "longitude": _safe_float(lng),
        "url": url,
        "is_offplan": is_offplan,
        "agent_name": _deep_get(raw, "contactName") or _deep_get(raw, "agency", "name"),
        "agent_phone": str(raw.get("phoneNumber", {}).get("phone", "")) if isinstance(raw.get("phoneNumber"), dict) else str(raw.get("phoneNumber", "")),
        "listed_date": raw.get("createdAt") or raw.get("listedDate"),
    }


# ─── HTML fallback ───────────────────────────────────────────────────

def _parse_html_fallback(html: str, purpose: str, city: str, area_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    cards = soup.select('article[role="Listing"], article[aria-label*="Listing"], article')

    for card in cards:
        try:
            price_el = card.select_one('[data-qa="price-value"], span.price, h3')
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = _extract_number(price_text)

            title_el = card.select_one("h2, h3, [data-qa='title']")
            title = title_el.get_text(strip=True) if title_el else ""

            link = card.select_one("a[href*='property'], a[href]")
            href = link["href"] if link else ""
            ext_id_match = re.search(r"(\d{6,})", href)
            ext_id = ext_id_match.group(1) if ext_id_match else ""
            if not ext_id or not price:
                continue

            specs_text = card.get_text(" ", strip=True)
            beds = _extract_int_near(specs_text, r"(\d+)\s*bed")
            baths = _extract_int_near(specs_text, r"(\d+)\s*bath")
            sqft = _extract_number_near(specs_text, r"([\d,]+)\s*sqft")

            results.append({
                "id": f"bayut_{ext_id}",
                "source": "bayut",
                "external_id": ext_id,
                "purpose": purpose,
                "property_type": "",
                "title": title,
                "price": price,
                "currency": "AED",
                "area_sqft": sqft,
                "bedrooms": beds,
                "bathrooms": baths,
                "city": city,
                "area_name": area_name,
                "location_full": "",
                "latitude": None,
                "longitude": None,
                "url": urljoin(BAYUT["base_url"], href) if href else "",
                "is_offplan": False,
                "agent_name": None,
                "agent_phone": None,
                "listed_date": None,
            })
        except Exception as exc:
            log.debug("HTML fallback card parse error: %s", exc)

    return results


# ─── Public API ──────────────────────────────────────────────────────

def fetch_bayut_listings(
    purpose: str,
    locations: list[dict],
) -> list[dict]:
    """
    Fetch listings from Bayut.  Requires valid cookies in data/bayut_cookies.json.
    If cookies are missing or expired, logs a warning and returns an empty list.
    """
    session = _get_session()
    if session is None:
        log.warning(
            "No Bayut cookies found. Run `python -c \"from scrapers.bayut import refresh_bayut_cookies; "
            "refresh_bayut_cookies()\"` to solve the captcha and save cookies, "
            "or manually place cookies in data/bayut_cookies.json"
        )
        return []

    all_listings: list[dict] = []

    for loc in locations:
        city = loc["city"]
        area_name = loc["name"]
        slug = loc["bayut_slug"]

        page = 1
        total_pages = 1

        while page <= min(total_pages, MAX_PAGES_PER_SEARCH):
            url = _build_url(purpose, city, slug, page)
            log.info("[bayut] %s p%d/%d — %s", area_name, page, total_pages, url)

            try:
                resp = session.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException as exc:
                log.warning("[bayut] Request failed for %s p%d: %s", area_name, page, exc)
                break

            html = resp.text

            # Check for bot challenge
            if "hb-challenge" in html or "cf-challenge" in html or "captcha" in html.lower():
                log.warning(
                    "[bayut] Bot challenge detected for %s — cookies may be expired. "
                    "Run `python main.py --refresh-bayut-cookies` to refresh.",
                    area_name,
                )
                break

            # Try __NEXT_DATA__ first
            next_data = _extract_next_data(html)
            if next_data:
                raw_listings = _listings_from_next_data(next_data)
                if page == 1:
                    total_pages = _page_count_from_next_data(next_data)
            else:
                # Fall back to HTML parsing
                log.debug("[bayut] No __NEXT_DATA__ found, using HTML fallback for %s p%d", area_name, page)
                raw_listings = _parse_html_fallback(html, purpose, city, area_name)

            if not raw_listings:
                log.debug("[bayut] No listings on %s p%d, stopping pagination", area_name, page)
                break

            for raw in raw_listings:
                listing = _normalise(raw, purpose, city, area_name)
                if listing:
                    all_listings.append(listing)

            log.debug("[bayut] %s p%d — got %d raw, %d total so far",
                      area_name, page, len(raw_listings), len(all_listings))

            page += 1
            if page <= min(total_pages, MAX_PAGES_PER_SEARCH):
                time.sleep(random.uniform(*REQUEST_DELAY))

    log.info("[bayut] Done — %d listings for purpose=%s", len(all_listings), purpose)
    return all_listings


# ─── Utility helpers ─────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _deep_get(d: dict, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _extract_number(text: str) -> float | None:
    text = text.replace(",", "").replace(" ", "")
    match = re.search(r"[\d.]+", text)
    return float(match.group()) if match else None


def _extract_int_near(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_number_near(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    return None
