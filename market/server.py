"""
UAE Market Intelligence — Shelved
Serves static "Coming Back Soon" page only.
"""

import os
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")
app.url_map.strict_slashes = False


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "uae-market-intel", "mode": "shelved"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
