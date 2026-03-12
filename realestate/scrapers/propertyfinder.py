"""
PropertyFinder.ae scraper
=========================
Strategy:
  1. Fetch search pages via HTTP GET using slug-based URLs.
  2. Extract __NEXT_DATA__ JSON (Next.js SSR data).
  3. Parse listings from searchResult.listings[].property
  4. Paginate using -N.html suffix pattern.
  5. HTML fallback with BeautifulSoup if __NEXT_DATA__ is absent.

URL patterns:
  Sale: /en/buy/{city}/properties-for-sale.html
        /en/buy/{city}/properties-for-sale-{page}.html
  Rent: /en/rent/{city}/properties-for-rent.html
        /en/rent/{city}/properties-for-rent-{page}.html

Public interface:  fetch_pf_listings(purpose, locations) → list[dict]
"""

import json
import random
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import (
    HEADERS,
    MAX_PAGES_PER_SEARCH,
    PROPERTYFINDER as PF,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
)
from utils.logger import get_logger

log = get_logger()

_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)


# ─── URL builder ─────────────────────────────────────────────────────

def _build_url(purpose: str, city_slug: str, page: int = 1) -> str:
    """
    Build PropertyFinder search URL.
    Sale:  /en/buy/{city}/properties-for-sale.html
           /en/buy/{city}/properties-for-sale.html?page=2
    Rent:  /en/rent/{city}/properties-for-rent.html
    """
    if purpose == "sale":
        cat = "buy"
        suffix = "for-sale"
    else:
        cat = "rent"
        suffix = "for-rent"

    base = f"{PF['base_url']}/en/{cat}/{city_slug}/properties-{suffix}.html"
    if page > 1:
        base += f"?page={page}"
    return base


def _build_area_url(purpose: str, city_slug: str, area_slug: str, page: int = 1) -> str:
    """Build area-specific URL (may not always have SSR data)."""
    if purpose == "sale":
        cat = "buy"
        suffix = "for-sale"
    else:
        cat = "rent"
        suffix = "for-rent"

    if page == 1:
        path = f"/en/{cat}/{city_slug}/{area_slug}/properties-{suffix}.html"
    else:
        path = f"/en/{cat}/{city_slug}/{area_slug}/properties-{suffix}-{page}.html"

    return f"{PF['base_url']}{path}"


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
        log.warning("PF __NEXT_DATA__ JSON parse error: %s", exc)
        return None


def _listings_from_next_data(data: dict) -> list[dict]:
    """Extract property objects from __NEXT_DATA__.
    
    PF nests data under searchResult.listings[] where each entry is:
      { "listing_type": "property", "property": { ... } }
    Also has searchResult.properties[] as a flatter list.
    """
    props = data.get("props", {}).get("pageProps", {})
    sr = props.get("searchResult", {})

    # Primary source: listings[].property (richest data)
    listings = sr.get("listings", [])
    if listings:
        results = []
        for entry in listings:
            if entry.get("listing_type") == "property":
                prop = entry.get("property")
                if prop:
                    results.append(prop)
        if results:
            return results

    # Fallback: properties[] array
    properties = sr.get("properties", [])
    if properties:
        return properties

    return []


def _get_pagination(data: dict) -> dict:
    """Extract pagination info from meta."""
    props = data.get("props", {}).get("pageProps", {})
    sr = props.get("searchResult", {})
    meta = sr.get("meta", {})
    return {
        "page": meta.get("page", 1),
        "total_count": meta.get("total_count", 0),
        "per_page": meta.get("per_page", 25),
        "page_count": meta.get("page_count", 0),
    }


# ─── Normaliser ──────────────────────────────────────────────────────

def _normalise(raw: dict, purpose: str, target_city: str, target_area: str | None = None) -> dict | None:
    ext_id = str(raw.get("id", ""))
    if not ext_id:
        return None

    # Price
    price_obj = raw.get("price", {})
    if isinstance(price_obj, dict):
        price = price_obj.get("value")
    else:
        price = price_obj
    if price is None:
        return None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None

    # Size
    size_obj = raw.get("size", {})
    if isinstance(size_obj, dict):
        area_sqft = _safe_float(size_obj.get("value"))
    else:
        area_sqft = _safe_float(size_obj or raw.get("area"))

    # Location
    loc = raw.get("location", {})
    if isinstance(loc, dict):
        location_full = loc.get("full_name", "")
        coords = loc.get("coordinates", {}) or {}
        lat = _safe_float(coords.get("lat"))
        lng = _safe_float(coords.get("lon") or coords.get("lng"))
        # Extract area from location path
        path_name = loc.get("path_name", "")  # e.g. "Abu Dhabi, Yas Island"
        loc_name = loc.get("name", "")        # e.g. "Gardenia Bay"
        # Derive area_name from the location hierarchy
        area_name = _extract_area_from_location(location_full, target_city)
    else:
        location_full = str(loc)
        lat = lng = None
        area_name = ""

    # Detect city from location
    city = target_city
    if "dubai" in location_full.lower():
        city = "dubai"
    elif "abu dhabi" in location_full.lower():
        city = "abu-dhabi"

    # Property type
    ptype = str(raw.get("property_type", "") or raw.get("type", "")).lower()

    # Off-plan detection
    completion = raw.get("completion_status", "") or raw.get("offering_type", "")
    is_offplan = "off" in str(completion).lower() or "plan" in str(completion).lower()

    # URL
    share_url = raw.get("share_url") or raw.get("details_path") or ""
    if share_url and not share_url.startswith("http"):
        share_url = urljoin(PF["base_url"], share_url)

    # Agent info
    agent = raw.get("agent", {}) or {}
    broker = raw.get("broker", {}) or {}

    return {
        "id": f"pf_{ext_id}",
        "source": "propertyfinder",
        "external_id": ext_id,
        "purpose": purpose,
        "property_type": ptype,
        "title": raw.get("title", ""),
        "price": price,
        "currency": price_obj.get("currency", "AED") if isinstance(price_obj, dict) else "AED",
        "area_sqft": area_sqft,
        "bedrooms": _safe_int(raw.get("bedrooms") or raw.get("bedrooms_value")),
        "bathrooms": _safe_int(raw.get("bathrooms") or raw.get("bathrooms_value")),
        "city": city,
        "area_name": area_name or target_area or "",
        "location_full": location_full,
        "latitude": lat,
        "longitude": lng,
        "url": share_url,
        "is_offplan": is_offplan,
        "agent_name": agent.get("name") or broker.get("name"),
        "agent_phone": str(agent.get("phone", "") or broker.get("phone", "")),
        "listed_date": raw.get("listed_date") or raw.get("created_at"),
    }


def _extract_area_from_location(full_name: str, city_slug: str) -> str:
    """
    Extract the primary area name from a full location string.
    e.g. "Gardenia Bay, Yas Island, Abu Dhabi" → "Yas Island"
         "Building A, Al Zeina, Al Raha Beach, Abu Dhabi" → "Al Raha Beach"
    """
    parts = [p.strip() for p in full_name.split(",")]
    # Remove city name (last part)
    if parts and parts[-1].strip().lower().replace(" ", "-") in ("abu-dhabi", "dubai", "sharjah", "ajman"):
        parts = parts[:-1]
    # The area is typically the second-to-last element (community level)
    if len(parts) >= 2:
        return parts[-1]
    elif len(parts) == 1:
        return parts[0]
    return ""


# ─── HTML fallback ───────────────────────────────────────────────────

def _parse_html_fallback(html: str, purpose: str, city: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    cards = soup.select('article[data-testid="property-card"]')
    if not cards:
        cards = soup.select("article")

    for card in cards:
        try:
            price_el = card.select_one('[data-testid="property-card-price"]')
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = _extract_number(price_text)

            title_el = card.select_one("h2, h3")
            title = title_el.get_text(strip=True) if title_el else ""

            link = card.select_one("a[href]")
            href = link["href"] if link else ""
            id_match = re.search(r"(\d{6,})", href)
            ext_id = id_match.group(1) if id_match else ""
            if not ext_id or not price:
                continue

            beds_el = card.select_one('[data-testid="property-card-spec-bedroom"]')
            baths_el = card.select_one('[data-testid="property-card-spec-bathroom"]')
            area_el = card.select_one('[data-testid="property-card-spec-area"]')
            loc_el = card.select_one('[data-testid="property-card-location"]')

            results.append({
                "id": f"pf_{ext_id}",
                "source": "propertyfinder",
                "external_id": ext_id,
                "purpose": purpose,
                "property_type": "",
                "title": title,
                "price": price,
                "currency": "AED",
                "area_sqft": _extract_number(area_el.get_text(strip=True)) if area_el else None,
                "bedrooms": _extract_int(beds_el.get_text(strip=True)) if beds_el else None,
                "bathrooms": _extract_int(baths_el.get_text(strip=True)) if baths_el else None,
                "city": city,
                "area_name": "",
                "location_full": loc_el.get_text(strip=True) if loc_el else "",
                "latitude": None,
                "longitude": None,
                "url": urljoin(PF["base_url"], href) if href else "",
                "is_offplan": False,
                "agent_name": None,
                "agent_phone": None,
                "listed_date": None,
            })
        except Exception as exc:
            log.debug("PF HTML fallback card parse error: %s", exc)

    return results


# ─── Public API ──────────────────────────────────────────────────────

def fetch_pf_listings(
    purpose: str,
    locations: list[dict],
) -> list[dict]:
    """
    Fetch listings from PropertyFinder for the given purpose ('sale' | 'rent').
    
    Strategy: Fetch city-wide listing pages (which always have data),
    then filter/tag by area based on the location field in each listing.
    """
    all_listings: list[dict] = []
    seen_ids: set[str] = set()

    # Group locations by city
    cities: dict[str, list[dict]] = {}
    for loc in locations:
        city = loc["city"]
        cities.setdefault(city, []).append(loc)

    for city_slug, city_locs in cities.items():
        area_names = {loc["name"] for loc in city_locs}
        page = 1
        max_pages = MAX_PAGES_PER_SEARCH

        log.info("PF [%s] %s — starting (areas: %s)", purpose, city_slug, ", ".join(area_names))

        while page <= max_pages:
            url = _build_url(purpose, city_slug, page)
            log.debug("GET %s", url)

            try:
                resp = _SESSION.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException as exc:
                log.error("PF request failed: %s — %s", url, exc)
                break

            html = resp.text

            # Strategy 1: __NEXT_DATA__
            next_data = _extract_next_data(html)
            if next_data:
                raw_hits = _listings_from_next_data(next_data)
                if not raw_hits:
                    log.debug("No listings in __NEXT_DATA__ for page %d — stopping", page)
                    break

                # Get pagination on first page
                if page == 1:
                    pag = _get_pagination(next_data)
                    total_pages = pag.get("page_count", 1)
                    max_pages = min(total_pages, MAX_PAGES_PER_SEARCH)
                    log.info("  Total: %d listings across %d pages (capped at %d)",
                             pag.get("total_count", 0), total_pages, max_pages)

                parsed = [_normalise(h, purpose, city_slug) for h in raw_hits]
                parsed = [p for p in parsed if p is not None]

                # Deduplicate
                new_count = 0
                for p in parsed:
                    if p["id"] not in seen_ids:
                        seen_ids.add(p["id"])
                        all_listings.append(p)
                        new_count += 1

                log.info("  page %d/%d → %d listings (%d new)", page, max_pages, len(parsed), new_count)
            else:
                # Strategy 2: HTML fallback
                log.info("  __NEXT_DATA__ not found — using HTML fallback")
                parsed = _parse_html_fallback(html, purpose, city_slug)
                for p in parsed:
                    if p["id"] not in seen_ids:
                        seen_ids.add(p["id"])
                        all_listings.append(p)
                log.info("  page %d → %d listings (HTML)", page, len(parsed))
                if not parsed:
                    break

            page += 1
            time.sleep(random.uniform(*REQUEST_DELAY))

        log.info("PF [%s] %s — done, total so far: %d", purpose, city_slug, len(all_listings))

    log.info("PF [%s] grand total: %d listings", purpose, len(all_listings))
    return all_listings


# ─── Utilities ───────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    if v is None: return None
    try: return float(v)
    except (TypeError, ValueError): return None

def _safe_int(v) -> int | None:
    if v is None: return None
    try: return int(float(v))
    except (TypeError, ValueError): return None

def _extract_number(text: str) -> float | None:
    nums = re.findall(r"[\d,]+\.?\d*", text.replace(",", ""))
    if nums:
        try: return float(nums[0])
        except ValueError: pass
    return None

def _extract_int(text: str) -> int | None:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None
