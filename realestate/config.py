"""
UAE Real Estate Monitor Bot — Configuration
============================================
All tuneable parameters live here: budget profiles, target areas,
property types, scoring thresholds, database path, and alert settings.
"""

import os
from pathlib import Path

# ─── Paths ─────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "listings.db"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ─── Scraper Settings ──────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30          # seconds per HTTP request
REQUEST_DELAY = (1.5, 3.5)   # random sleep range between requests (seconds)
MAX_PAGES_PER_SEARCH = 20    # pagination cap per search combination
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept": "application/json, text/html, */*",
}

# ─── Target Locations ──────────────────────────────────────────────────────
# Each entry: { display_name, bayut_slug, pf_location_id }
LOCATIONS = [
    # Abu Dhabi
    {"name": "Al Reem Island",      "city": "abu-dhabi", "bayut_slug": "al-reem-island",      "pf_location_id": "108"},
    {"name": "Yas Island",          "city": "abu-dhabi", "bayut_slug": "yas-island",           "pf_location_id": "528"},
    {"name": "Saadiyat Island",     "city": "abu-dhabi", "bayut_slug": "saadiyat-island",      "pf_location_id": "527"},
    {"name": "Al Raha Beach",       "city": "abu-dhabi", "bayut_slug": "al-raha-beach",        "pf_location_id": "286"},
    {"name": "Khalifa City",        "city": "abu-dhabi", "bayut_slug": "khalifa-city",         "pf_location_id": "160"},
    {"name": "Mohammed Bin Zayed City", "city": "abu-dhabi", "bayut_slug": "mohammed-bin-zayed-city", "pf_location_id": "173"},
    # Dubai
    {"name": "Dubai Marina",        "city": "dubai", "bayut_slug": "dubai-marina",         "pf_location_id": "36"},
    {"name": "Downtown Dubai",      "city": "dubai", "bayut_slug": "downtown-dubai",       "pf_location_id": "37"},
    {"name": "Business Bay",        "city": "dubai", "bayut_slug": "business-bay",         "pf_location_id": "584"},
    {"name": "Jumeirah Village Circle", "city": "dubai", "bayut_slug": "jumeirah-village-circle", "pf_location_id": "50"},
    {"name": "Dubai Hills Estate",  "city": "dubai", "bayut_slug": "dubai-hills-estate",   "pf_location_id": "5002"},
    {"name": "Palm Jumeirah",       "city": "dubai", "bayut_slug": "palm-jumeirah",        "pf_location_id": "39"},
]

# ─── Property Types ────────────────────────────────────────────────────────
PROPERTY_TYPES = ["apartment", "villa", "townhouse", "penthouse"]

# ─── Budget Profiles ───────────────────────────────────────────────────────
# Defines price windows per purpose.  Used to filter search queries.
BUDGET_PROFILES = {
    "sale": {
        "min_price": 400_000,     # AED
        "max_price": 10_000_000,  # AED
    },
    "rent": {
        "min_price": 20_000,      # AED / year
        "max_price": 500_000,     # AED / year
    },
}

# ─── Opportunity Scoring ────────────────────────────────────────────────────
SCORING = {
    "price_below_avg_pct":  10,     # flag if >10% below area avg per sqft
    "min_gross_yield":      6.0,    # flag if gross rental yield > 6%
    "price_drop_pct":       5.0,    # flag if price dropped > 5% since last seen
    "alert_threshold":      40,     # composite score (0-100) to include in report
    "top_n_report":         20,     # max listings in the daily PDF
    "weights": {                    # yield-heavy profile
        "rental_yield":     0.40,
        "price_below_avg":  0.25,
        "price_drop":       0.20,
        "off_plan_launch":  0.15,
    },
}

# ─── Email (Brevo Transactional API — sends daily PDF report) ───────
# Setup: sign up at https://app.brevo.com, get API key from Settings → API Keys
# Sender email MUST be verified in Brevo (Settings → Senders & IP)
EMAIL = {
    "brevo_api_key":  os.getenv("BREVO_API_KEY", ""),
    "sender_email":   os.getenv("SENDER_EMAIL", ""),       # must be verified in Brevo
    "sender_name":    os.getenv("SENDER_NAME", "RE Monitor Bot"),
    "recipient":      os.getenv("REPORT_RECIPIENT", "rashed@aldhaheri.co"),
}

# ─── Bayut-specific ────────────────────────────────────────────────────────
BAYUT = {
    "base_url": "https://www.bayut.com",
    # Bayut embeds listing data inside __NEXT_DATA__ JSON on each page.
    # URL pattern:  /for-sale/property/{city}/{area_slug}/
    # Rental:       /to-rent/property/{city}/{area_slug}/
    "sale_path_tpl":  "/for-sale/property/{city}/{slug}/",
    "rent_path_tpl":  "/to-rent/property/{city}/{slug}/",
    "page_param":     "page",   # ?page=2
}

# ─── PropertyFinder-specific ─────────────────────────────────────────────────
PROPERTYFINDER = {
    "base_url": "https://www.propertyfinder.ae",
    # PF also uses __NEXT_DATA__; search endpoint mirrors the URL.
    # Buy:  /en/search?l={loc_id}&c=1&page=N
    # Rent: /en/search?l={loc_id}&c=2&page=N
    "search_path": "/en/search",
    "category_buy":  1,
    "category_rent": 2,
}
