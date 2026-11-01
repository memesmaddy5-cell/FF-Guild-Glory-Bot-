"""
Safe, read-only Free Fire guild information dashboard.

This version deliberately does NOT create/store guest credentials, generate
fake accounts, call Free Fire login/token endpoints, or automate in-game actions.

Render start command:
    gunicorn app:app --workers 1 --threads 4 --timeout 120

Expected project layout:
    app.py
    templates/index.html
    templates/dashboard.html
"""

import os
import time
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

GUILD_API_URL = os.environ.get(
    "GUILD_API_URL",
    "https://free-ff-api-src-5plp.onrender.com/api/v1/guildInfo",
)
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "8"))
_guild_cache = {}


def _empty_guild(guild_id: str, region: str) -> dict:
    return {
        "guildFound": False,
        "guildId": guild_id,
        "guildName": "Unknown Guild",
        "guildLevel": 0,
        "memberNum": 0,
        "capacity": 35,
        "guildOwner": "",
        "region": region,
    }


def fetch_guild_info(guild_id: str, region: str = "IND") -> dict:
    """Fetch public guild information from the configured information API."""
    now = time.time()
    cache_key = (guild_id, region)
    cached = _guild_cache.get(cache_key)
    if cached and now - cached["timestamp"] < CACHE_TTL_SECONDS:
        return dict(cached["data"])

    result = _empty_guild(guild_id, region)
    try:
        response = requests.get(
            GUILD_API_URL,
            params={"region": region, "guildID": guild_id},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        result.update({
            "guildFound": True,
            "guildName": data.get("clanName", data.get("GuildName", "Unknown Guild")),
            "guildLevel": data.get("clanLevel", data.get("GuildLevel", 0)),
            "memberNum": data.get("memberNum", data.get("GuildMember", 0)),
            "capacity": data.get("capacity", data.get("GuildCapacity", 35)),
            "guildOwner": data.get("captainId", data.get("GuildOwner", "")),
        })
    except (requests.RequestException, ValueError, TypeError):
        pass

    _guild_cache[cache_key] = {"data": dict(result), "timestamp": now}
    return result


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.get("/health")
def health():
    return jsonify({
        "status": "alive",
        "mode": "read-only",
        "time": datetime.now(timezone.utc).isoformat(),
    })


@app.get("/api/guild/info")
def api_guild_info():
    guild_id = request.args.get("guild_id", "").strip()
    region = request.args.get("region", "IND").strip().upper()
    if not guild_id.isdigit():
        return jsonify({"error": "A numeric guild_id is required"}), 400
    if region not in {"IND", "SG", "ID", "BR", "US", "TH", "VN", "TW", "ME", "PK", "BD"}:
        return jsonify({"error": "Unsupported region"}), 400
    return jsonify(fetch_guild_info(guild_id, region))


@app.get("/api/status")
def api_status():
    return jsonify({
        "guild_id": "",
        "guild_info": {},
        "running": False,
        "bots": {},
        "stats": {
            "total_glory": 0,
            "matches": 0,
            "success": 0,
            "failed": 0,
            "glory_per_hour": 0,
            "active_bots": 0,
            "bot_count": 0,
            "start_time": None,
            "running_hours": 0,
        },
        "mode": "read-only",
        "message": "In-game automation is disabled in this safe build.",
    })


@app.post("/api/start")
@app.post("/api/stop")
def automation_disabled():
    return jsonify({
        "success": False,
        "message": "In-game automation is disabled. This deployment only provides read-only guild information.",
    }), 403


@app.get("/api/guests/count")
def guests_count_disabled():
    return jsonify({
        "total": 0,
        "working": 0,
        "message": "Guest-account storage is disabled in this safe build.",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
