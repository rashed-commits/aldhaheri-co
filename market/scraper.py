"""
UAE Market Intelligence — Scraping & AI Classification Pipeline

Scrapes posts from Reddit, Twitter/X, LinkedIn, Facebook Groups, and News/Forums,
classifies them with GPT-4o-mini, and stores signals in the existing SQLite database.

Usage:
    python scraper.py          # Run full pipeline (for cron)
    from scraper import run_pipeline  # Import for API trigger
"""

import json
import logging
import os
import sqlite3
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scraper")

DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "data", "market_intel.db"),
)
MAX_ITEMS = int(os.environ.get("SCRAPE_MAX_ITEMS_PER_SOURCE", "20"))

# ── Lazy client helpers ──────────────────────────────────────────────
_apify_client = None
_tavily_client = None
_openai_client = None


def _apify():
    global _apify_client
    if _apify_client is None:
        from apify_client import ApifyClient
        _apify_client = ApifyClient(os.environ["APIFY_TOKEN"])
    return _apify_client


def _tavily():
    global _tavily_client
    if _tavily_client is None:
        from tavily import TavilyClient
        _tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _tavily_client


def _openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _openai_client


# ── Scrapers ─────────────────────────────────────────────────────────
# Each returns a list of dicts: {text, source_url, platform, raw_text, date}


def scrape_reddit():
    """Scrape UAE-related Reddit content via Tavily (Apify gets 403 blocked)."""
    log.info("Scraping Reddit (via Tavily) …")
    posts = []
    queries = [
        "site:reddit.com/r/dubai business opportunity",
        "site:reddit.com/r/UAE startup market",
    ]
    try:
        for query in queries:
            results = _tavily().search(
                query=query,
                max_results=min(MAX_ITEMS, 10),
                include_raw_content=True,
            )
            for item in results.get("results", []):
                text = item.get("raw_content") or item.get("content", "")
                if not text.strip() or len(text.strip()) < 20:
                    continue
                posts.append({
                    "text": text[:2000],
                    "source_url": item.get("url", ""),
                    "platform": "Reddit",
                    "raw_text": text[:2000],
                    "date": datetime.now().isoformat(),
                })
            if len(posts) >= MAX_ITEMS:
                posts = posts[:MAX_ITEMS]
                break
    except Exception as e:
        log.error("Reddit (Tavily) scraper failed: %s", e)
    log.info("Reddit: %d posts", len(posts))
    return posts


def scrape_twitter():
    """Scrape UAE-related tweets via Apify."""
    log.info("Scraping Twitter/X …")
    posts = []
    try:
        run = _apify().actor("apidojo/tweet-scraper").call(
            run_input={
                "searchTerms": ["UAE startup", "Dubai business", "Abu Dhabi market"],
                "maxItems": MAX_ITEMS,
                "sort": "Latest",
                "proxy": {"useApifyProxy": True},
            },
            timeout_secs=120,
        )
        for item in _apify().dataset(run["defaultDatasetId"]).iterate_items():
            text = item.get("full_text", item.get("text", ""))
            tweet_id = item.get("id_str", item.get("id", ""))
            user = item.get("user", {}).get("screen_name", "")
            url = f"https://x.com/{user}/status/{tweet_id}" if user and tweet_id else ""
            posts.append({
                "text": text,
                "source_url": url,
                "platform": "X / Twitter",
                "raw_text": text,
                "date": item.get("created_at", datetime.now().isoformat()),
            })
    except Exception as e:
        log.error("Twitter scraper failed: %s", e)
    log.info("Twitter: %d posts", len(posts))
    return posts


def scrape_linkedin():
    """Scrape LinkedIn posts about UAE business via Apify."""
    log.info("Scraping LinkedIn …")
    posts = []
    try:
        run = _apify().actor("curious_coder/linkedin-post-search-scraper").call(
            run_input={
                "searchTerms": ["UAE market opportunity", "Dubai startup"],
                "maxItems": MAX_ITEMS,
                "proxy": {"useApifyProxy": True},
            },
            timeout_secs=120,
        )
        for item in _apify().dataset(run["defaultDatasetId"]).iterate_items():
            text = item.get("text", item.get("commentary", ""))
            posts.append({
                "text": text,
                "source_url": item.get("url", item.get("postUrl", "")),
                "platform": "LinkedIn",
                "raw_text": text,
                "date": item.get("postedAt", datetime.now().isoformat()),
            })
    except Exception as e:
        log.error("LinkedIn scraper failed: %s", e)
    log.info("LinkedIn: %d posts", len(posts))
    return posts


def scrape_facebook():
    """Scrape public UAE Facebook content via Tavily (Facebook blocks bots)."""
    log.info("Scraping Facebook (via Tavily) …")
    posts = []
    queries = [
        "site:facebook.com Dubai business opportunities",
        "site:facebook.com UAE startups community",
        "site:facebook.com Dubai expats jobs housing",
    ]
    try:
        for query in queries:
            results = _tavily().search(
                query=query,
                max_results=min(MAX_ITEMS, 10),
                include_raw_content=True,
            )
            for item in results.get("results", []):
                text = item.get("raw_content") or item.get("content", "")
                url = item.get("url", "")
                if not text.strip() or len(text.strip()) < 20:
                    continue
                posts.append({
                    "text": text[:2000],
                    "source_url": url,
                    "platform": "Facebook",
                    "raw_text": text[:2000],
                    "date": datetime.now().isoformat(),
                })
            if len(posts) >= MAX_ITEMS:
                posts = posts[:MAX_ITEMS]
                break
    except Exception as e:
        log.error("Facebook (Tavily) scraper failed: %s", e)
    log.info("Facebook: %d posts", len(posts))
    return posts


def scrape_google_maps():
    """Scrape Google Maps reviews via Tavily (Apify per-item billing too expensive)."""
    log.info("Scraping Google Maps (via Tavily) …")
    posts = []
    queries = [
        "site:google.com/maps Dubai restaurant reviews complaints",
        "site:google.com/maps Abu Dhabi clinic reviews",
    ]
    try:
        for query in queries:
            results = _tavily().search(
                query=query,
                max_results=min(MAX_ITEMS, 10),
                include_raw_content=True,
            )
            for item in results.get("results", []):
                text = item.get("raw_content") or item.get("content", "")
                if not text.strip() or len(text.strip()) < 20:
                    continue
                posts.append({
                    "text": text[:2000],
                    "source_url": item.get("url", ""),
                    "platform": "Google Reviews",
                    "raw_text": text[:2000],
                    "date": datetime.now().isoformat(),
                })
            if len(posts) >= MAX_ITEMS:
                posts = posts[:MAX_ITEMS]
                break
    except Exception as e:
        log.error("Google Maps (Tavily) scraper failed: %s", e)
    log.info("Google Maps: %d reviews", len(posts))
    return posts


def scrape_tiktok():
    """Scrape UAE-related TikTok posts via Apify."""
    log.info("Scraping TikTok …")
    posts = []
    try:
        run = _apify().actor("clockworks/tiktok-scraper").call(
            run_input={
                "searchQueries": ["Dubai business", "UAE startup", "life in Dubai"],
                "maxItems": MAX_ITEMS,
                "proxy": {"useApifyProxy": True},
            },
            timeout_secs=180,
        )
        for item in _apify().dataset(run["defaultDatasetId"]).iterate_items():
            text = item.get("text", item.get("desc", ""))
            video_id = item.get("id", "")
            author = item.get("authorMeta", {}).get("name", item.get("author", ""))
            url = item.get("webVideoUrl", f"https://www.tiktok.com/@{author}/video/{video_id}" if author and video_id else "")
            posts.append({
                "text": text,
                "source_url": url,
                "platform": "TikTok",
                "raw_text": text,
                "date": item.get("createTimeISO", datetime.now().isoformat()),
            })
    except Exception as e:
        log.error("TikTok scraper failed: %s", e)
    log.info("TikTok: %d posts", len(posts))
    return posts


def scrape_instagram():
    """Scrape UAE-related Instagram posts via Apify."""
    log.info("Scraping Instagram …")
    posts = []
    try:
        run = _apify().actor("apify/instagram-scraper").call(
            run_input={
                "search": "Dubai business",
                "searchType": "hashtag",
                "resultsLimit": MAX_ITEMS,
                "proxy": {"useApifyProxy": True},
            },
            timeout_secs=180,
        )
        for item in _apify().dataset(run["defaultDatasetId"]).iterate_items():
            caption = item.get("caption", "")
            shortcode = item.get("shortCode", item.get("shortcode", ""))
            url = item.get("url", f"https://www.instagram.com/p/{shortcode}/" if shortcode else "")
            posts.append({
                "text": caption,
                "source_url": url,
                "platform": "Instagram",
                "raw_text": caption,
                "date": item.get("timestamp", datetime.now().isoformat()),
            })
    except Exception as e:
        log.error("Instagram scraper failed: %s", e)
    log.info("Instagram: %d posts", len(posts))
    return posts


def scrape_youtube():
    """Scrape YouTube UAE business content via Tavily (Apify two-step was 2 paid runs for 0 results)."""
    log.info("Scraping YouTube (via Tavily) …")
    posts = []
    queries = [
        "site:youtube.com UAE business opportunity 2026",
        "site:youtube.com Dubai startup market",
    ]
    try:
        for query in queries:
            results = _tavily().search(
                query=query,
                max_results=min(MAX_ITEMS, 10),
                include_raw_content=True,
            )
            for item in results.get("results", []):
                text = item.get("raw_content") or item.get("content", "")
                if not text.strip() or len(text.strip()) < 20:
                    continue
                posts.append({
                    "text": text[:2000],
                    "source_url": item.get("url", ""),
                    "platform": "YouTube",
                    "raw_text": text[:2000],
                    "date": datetime.now().isoformat(),
                })
            if len(posts) >= MAX_ITEMS:
                posts = posts[:MAX_ITEMS]
                break
    except Exception as e:
        log.error("YouTube (Tavily) scraper failed: %s", e)
    log.info("YouTube: %d posts", len(posts))
    return posts


def scrape_dubizzle():
    """Scrape Dubizzle/classifieds UAE content via Tavily (Apify actor returned 0 results)."""
    log.info("Scraping Dubizzle (via Tavily) …")
    posts = []
    queries = [
        "site:dubizzle.com Dubai businesses for sale",
        "site:dubizzle.com UAE property market trends",
    ]
    try:
        for query in queries:
            results = _tavily().search(
                query=query,
                max_results=min(MAX_ITEMS, 10),
                include_raw_content=True,
            )
            for item in results.get("results", []):
                text = item.get("raw_content") or item.get("content", "")
                if not text.strip() or len(text.strip()) < 20:
                    continue
                posts.append({
                    "text": text[:2000],
                    "source_url": item.get("url", ""),
                    "platform": "Dubizzle",
                    "raw_text": text[:2000],
                    "date": datetime.now().isoformat(),
                })
            if len(posts) >= MAX_ITEMS:
                posts = posts[:MAX_ITEMS]
                break
    except Exception as e:
        log.error("Dubizzle (Tavily) scraper failed: %s", e)
    log.info("Dubizzle: %d listings", len(posts))
    return posts


def scrape_telegram():
    """Scrape UAE Telegram content via Tavily (channels behind login wall on Apify)."""
    log.info("Scraping Telegram (via Tavily) …")
    posts = []
    queries = [
        "site:t.me UAE jobs Dubai business",
        "site:t.me UAE news market opportunity",
    ]
    try:
        for query in queries:
            results = _tavily().search(
                query=query,
                max_results=min(MAX_ITEMS, 10),
                include_raw_content=True,
            )
            for item in results.get("results", []):
                text = item.get("raw_content") or item.get("content", "")
                if not text.strip() or len(text.strip()) < 20:
                    continue
                posts.append({
                    "text": text[:2000],
                    "source_url": item.get("url", ""),
                    "platform": "Telegram",
                    "raw_text": text[:2000],
                    "date": datetime.now().isoformat(),
                })
            if len(posts) >= MAX_ITEMS:
                posts = posts[:MAX_ITEMS]
                break
    except Exception as e:
        log.error("Telegram (Tavily) scraper failed: %s", e)
    log.info("Telegram: %d messages", len(posts))
    return posts


def scrape_news():
    """Search UAE business news and forums via Tavily."""
    log.info("Scraping News/Forums …")
    posts = []
    queries = [
        "UAE startup market opportunity 2026",
        "Dubai business pain point",
        "Abu Dhabi fintech investment",
    ]
    try:
        for query in queries:
            results = _tavily().search(
                query=query,
                max_results=MAX_ITEMS // len(queries),
                include_domains=[
                    "gulfnews.com",
                    "thenationalnews.com",
                    "arabianbusiness.com",
                    "khaleejtimes.com",
                    "zawya.com",
                ],
            )
            for r in results.get("results", []):
                posts.append({
                    "text": f"{r.get('title', '')} — {r.get('content', '')}",
                    "source_url": r.get("url", ""),
                    "platform": "News",
                    "raw_text": r.get("content", ""),
                    "date": r.get("published_date", datetime.now().isoformat()),
                })
    except Exception as e:
        log.error("News scraper failed: %s", e)
    log.info("News: %d posts", len(posts))
    return posts


# ── Deduplication ────────────────────────────────────────────────────

def get_existing_urls(conn):
    """Return a set of source_url values already in the database."""
    rows = conn.execute("SELECT source_url FROM signals WHERE source_url IS NOT NULL AND source_url != ''").fetchall()
    return {row[0] for row in rows}


def deduplicate(posts, existing_urls):
    """Remove posts whose source_url already exists in the DB."""
    seen = set()
    unique = []
    for p in posts:
        url = p.get("source_url", "").strip()
        if not url or url in existing_urls or url in seen:
            continue
        seen.add(url)
        unique.append(p)
    return unique


# ── AI Classification ────────────────────────────────────────────────

CLASSIFY_PROMPT = """\
You are a UAE market intelligence analyst. Given a social media post or news snippet,
determine if it contains a meaningful business signal for the UAE market.

Respond with ONLY a valid JSON object (no markdown fences, no extra text):
{
  "relevant": true/false,
  "title": "concise English title (max 80 chars)",
  "arabic_title": "Arabic translation of title",
  "summary": "2-3 sentence summary explaining the market signal",
  "type": "trending | pain_point | opportunity | mention",
  "sector": "one of: Fintech, Food & Beverage, Healthcare, Education, Real Estate, Logistics, Tourism, Retail, Technology",
  "priority": "High | Medium | Low",
  "score": 1-100 (relevance and impact score),
  "keywords": "comma,separated,keywords"
}

Set relevant=false if the post is spam, off-topic, or has no business insight.
"""


def classify_post(post):
    """Send a post to GPT-4o-mini and return structured classification."""
    text = (post.get("text") or "")[:2000]
    if not text.strip() or len(text.strip()) < 20:
        return None
    try:
        resp = _openai().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": CLASSIFY_PROMPT},
                {"role": "user", "content": f"Platform: {post['platform']}\nURL: {post['source_url']}\n\nPost:\n{text}"},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        log.error("Classification failed for %s: %s", post.get("source_url", "?"), e)
        return None


# ── Storage ──────────────────────────────────────────────────────────

def store_signal(conn, post, classification):
    """Insert a classified signal into the database."""
    conn.execute(
        """INSERT INTO signals
        (title, arabic_title, summary, type, sector, platform, priority,
         score, mentions, keywords, raw_text, source_url, date_collected, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            classification.get("title", ""),
            classification.get("arabic_title", ""),
            classification.get("summary", ""),
            classification.get("type", "trending"),
            classification.get("sector", "Technology"),
            post.get("platform", ""),
            classification.get("priority", "Medium"),
            classification.get("score", 50),
            1,
            classification.get("keywords", ""),
            post.get("raw_text", ""),
            post.get("source_url", ""),
            post.get("date", datetime.now().strftime("%Y-%m-%d")),
            "scraped",
        ),
    )


# ── Pipeline Orchestrator ────────────────────────────────────────────

def run_pipeline():
    """Scrape → Deduplicate → Classify → Store.  Returns a summary dict."""
    log.info("=== Pipeline starting ===")
    start = datetime.now()

    # 1. Scrape from all sources
    all_posts = []
    for scraper in [scrape_reddit, scrape_twitter, scrape_linkedin, scrape_facebook,
                     scrape_google_maps, scrape_tiktok, scrape_instagram,
                     scrape_youtube, scrape_dubizzle, scrape_telegram, scrape_news]:
        all_posts.extend(scraper())
    log.info("Total raw posts: %d", len(all_posts))

    # 2. Deduplicate
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    existing = get_existing_urls(conn)
    posts = deduplicate(all_posts, existing)
    log.info("After dedup: %d new posts", len(posts))

    # 3. Classify & 4. Store
    inserted = 0
    skipped = 0
    errors = 0
    for post in posts:
        result = classify_post(post)
        if result is None:
            errors += 1
            continue
        if not result.get("relevant", False):
            skipped += 1
            continue
        try:
            store_signal(conn, post, result)
            inserted += 1
        except Exception as e:
            log.error("DB insert failed: %s", e)
            errors += 1

    conn.commit()

    # Update metadata
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value, updated_at) VALUES ('last_scrape', ?, ?)",
        (json.dumps({"inserted": inserted, "skipped": skipped, "errors": errors}), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    elapsed = (datetime.now() - start).total_seconds()
    summary = {
        "scraped": len(all_posts),
        "new": len(posts),
        "inserted": inserted,
        "skipped_irrelevant": skipped,
        "errors": errors,
        "elapsed_seconds": round(elapsed, 1),
    }
    log.info("=== Pipeline finished: %s ===", summary)
    return summary


# ── Opportunity Generation ─────────────────────────────────────────

OPP_PROMPT = """\
You are a UAE market strategist. Given a list of market signals (scraped from social media, news, reviews), \
synthesize the top 10 concrete business opportunities for the UAE market.

Return exactly 5 SERVICE-based opportunities and 5 PRODUCT-based opportunities.
- Service: consulting, platforms, SaaS, marketplaces, delivery networks, etc.
- Product: physical products, hardware, consumer goods, food brands, etc.

For each opportunity, return a JSON object:
{
  "name": "catchy startup name (1-2 words)",
  "concept": "2-3 sentence business concept description",
  "sector": "matching sector from signals",
  "opp_type": "service" or "product",
  "target_market": "who buys this",
  "revenue_model": "how it makes money",
  "competition": "current alternatives and why they fall short",
  "gap_severity": 1-5 (how severe is the market gap),
  "composite_score": 1-99 (overall opportunity strength),
  "signal_ids": [list of signal IDs that support this opportunity]
}

Respond with ONLY a valid JSON array of 10 objects (no markdown fences, no extra text).
Score higher for: multiple supporting signals, high pain-point density, clear revenue model, weak competition.
"""


def generate_opportunities():
    """Read signals from DB, ask GPT-4o-mini to synthesize opportunities, store them."""
    log.info("=== Generating opportunities ===")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, title, summary, type, sector, platform, priority, score FROM signals ORDER BY score DESC LIMIT 100").fetchall()
    if not rows:
        conn.close()
        log.info("No signals found, skipping opportunity generation")
        return {"generated": 0}

    # Build signal summary for the prompt
    signal_text = "\n".join(
        f"[ID:{r['id']}] ({r['type']}, {r['sector']}, {r['platform']}, priority={r['priority']}, score={r['score']}) {r['title']} — {r['summary']}"
        for r in rows
    )

    try:
        resp = _openai().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": OPP_PROMPT},
                {"role": "user", "content": f"Here are the current market signals:\n\n{signal_text}"},
            ],
            temperature=0.4,
            max_tokens=4000,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        opps = json.loads(raw)
    except Exception as e:
        conn.close()
        log.error("Opportunity generation failed: %s", e)
        return {"generated": 0, "error": str(e)}

    # Clear old opportunities and insert new ones
    conn.execute("DELETE FROM opportunities")
    count = 0
    for opp in opps:
        try:
            conn.execute(
                """INSERT INTO opportunities
                (name, concept, sector, opp_type, target_market, revenue_model,
                 competition, gap_severity, composite_score, signal_ids)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    opp.get("name", ""),
                    opp.get("concept", ""),
                    opp.get("sector", ""),
                    opp.get("opp_type", "service"),
                    opp.get("target_market", ""),
                    opp.get("revenue_model", ""),
                    opp.get("competition", ""),
                    opp.get("gap_severity", 3),
                    opp.get("composite_score", 50),
                    json.dumps(opp.get("signal_ids", [])),
                ),
            )
            count += 1
        except Exception as e:
            log.error("Failed to insert opportunity: %s", e)
    conn.commit()
    conn.close()
    log.info("Generated %d opportunities", count)
    return {"generated": count}


if __name__ == "__main__":
    run_pipeline()
    generate_opportunities()
