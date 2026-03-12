"""
UAE Market Intelligence — Backend Server
Serves signal data from SQLite database via Flask
"""

import json
import sqlite3
import os
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from jose import jwt, JWTError

app = Flask(__name__, static_folder="static", static_url_path="")
app.url_map.strict_slashes = False
CORS(app, supports_credentials=True, origins=[
    "https://aldhaheri.co",
    "https://market.aldhaheri.co",
    "http://localhost:*",
])

JWT_SECRET = os.environ.get("JWT_SECRET", "")


def require_auth(f):
    """Decorator that validates JWT from session cookie set by aldhaheri.co."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("session")
        if not token:
            return jsonify({"error": "Not authenticated"}), 401
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            request.user = payload
        except JWTError:
            return jsonify({"error": "Invalid session"}), 401
        return f(*args, **kwargs)
    return decorated

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data", "market_intel.db"))


# ===================== DB SETUP =====================
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        arabic_title TEXT,
        summary TEXT,
        type TEXT CHECK(type IN ('trending','pain_point','opportunity','mention')),
        sector TEXT,
        platform TEXT,
        priority TEXT CHECK(priority IN ('High','Medium','Low')),
        score INTEGER,
        mentions INTEGER DEFAULT 0,
        keywords TEXT,
        raw_text TEXT,
        source_url TEXT,
        date_collected TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS platforms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT,
        active BOOLEAN DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sectors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        concept TEXT,
        sector TEXT,
        opp_type TEXT CHECK(opp_type IN ('service','product')),
        target_market TEXT,
        revenue_model TEXT,
        competition TEXT,
        gap_severity INTEGER DEFAULT 3,
        composite_score INTEGER DEFAULT 0,
        signal_ids TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()

    # Migration: add 'source' column to distinguish seed vs scraped data
    try:
        conn.execute("ALTER TABLE signals ADD COLUMN source TEXT DEFAULT 'seed'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    conn.close()


# ===================== HELPERS =====================
def rows_to_signals(rows):
    signals = []
    for row in rows:
        d = dict(row)
        d["keywords"] = [k.strip() for k in d["keywords"].split(",") if k.strip()] if d.get("keywords") else []
        signals.append(d)
    return signals


# ===================== ROUTES =====================
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/health")
def health():
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "ok", "service": "uae-market-intel"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "service": "uae-market-intel", "error": str(e)}), 500


@app.route("/api/auth/verify")
@require_auth
def verify_auth_endpoint():
    return jsonify({"valid": True, "user": request.user.get("sub")})


@app.route("/api")
@require_auth
def api():
    try:
        action = request.args.get("action", "all")
        conn = get_db()

        if action == "all":
            limit = request.args.get("limit", 200, type=int)
            rows = conn.execute("SELECT * FROM signals ORDER BY score DESC, id ASC LIMIT ?", (limit,)).fetchall()
            signals = rows_to_signals(rows)
            result = {"signals": signals, "count": len(signals), "timestamp": datetime.now().isoformat()}

        elif action == "stats":
            c = conn.cursor()
            total = c.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            high = c.execute("SELECT COUNT(*) FROM signals WHERE priority='High'").fetchone()[0]
            sector_count = c.execute("SELECT COUNT(DISTINCT sector) FROM signals").fetchone()[0]
            platform_count = c.execute("SELECT COUNT(DISTINCT platform) FROM signals").fetchone()[0]
            by_type = {}
            for row in c.execute("SELECT type, COUNT(*) as cnt FROM signals GROUP BY type").fetchall():
                by_type[row["type"]] = row["cnt"]
            result = {"total": total, "high_priority": high, "sectors": sector_count, "platforms": platform_count, "by_type": by_type}

        elif action == "sector":
            sector = request.args.get("sector", "")
            rows = conn.execute("SELECT * FROM signals WHERE sector=? ORDER BY score DESC", (sector,)).fetchall()
            signals = rows_to_signals(rows)
            result = {"signals": signals, "sector": sector, "count": len(signals)}

        elif action == "platform":
            platform = request.args.get("platform", "")
            rows = conn.execute("SELECT * FROM signals WHERE platform=? ORDER BY score DESC", (platform,)).fetchall()
            signals = rows_to_signals(rows)
            result = {"signals": signals, "platform": platform, "count": len(signals)}

        elif action == "search":
            query = request.args.get("q", "")
            q = f"%{query}%"
            rows = conn.execute(
                """SELECT * FROM signals WHERE
                title LIKE ? OR summary LIKE ? OR keywords LIKE ? OR arabic_title LIKE ?
                ORDER BY score DESC""",
                (q, q, q, q),
            ).fetchall()
            signals = rows_to_signals(rows)
            result = {"signals": signals, "query": query, "count": len(signals)}

        else:
            result = {"error": "Unknown action", "valid_actions": ["all", "stats", "sector", "platform", "search"]}

        conn.close()
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route("/api/opportunities")
@require_auth
def get_opportunities():
    """Return stored opportunities."""
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM opportunities ORDER BY composite_score DESC").fetchall()
        opps = []
        for row in rows:
            d = dict(row)
            d["signal_ids"] = json.loads(d["signal_ids"]) if d.get("signal_ids") else []
            opps.append(d)
        conn.close()
        return jsonify({"opportunities": opps, "count": len(opps)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/opportunities/generate", methods=["POST"])
@require_auth
def generate_opportunities():
    """Generate business opportunities from current signals using AI."""
    try:
        from scraper import generate_opportunities as gen_opps
        result = gen_opps()
        return jsonify({"status": "ok", **result})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "type": type(e).__name__}), 500


@app.route("/api/scrape", methods=["POST"])
@require_auth
def trigger_scrape():
    """Manually trigger the scraping pipeline."""
    try:
        from scraper import run_pipeline
        summary = run_pipeline()
        return jsonify({"status": "ok", **summary})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "type": type(e).__name__}), 500


# ===================== INIT =====================
with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
