#!/usr/bin/env python3
"""
Sumit x mods - Video Stream v4.0 [RANDOM IDs]
- Random 10-char IDs (no guess)
- YouTube ✅, Pinterest ✅, Direct ✅
"""

import os, re, json, time, sqlite3, secrets, string
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.secret_key = os.urandom(24).hex()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")
LINK_CACHE_DURATION = 3600

# ═══════════════ RANDOM ID GENERATOR ═══════════════
def generate_id(length=10):
    chars = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

# ═══════════════ DATABASE ═══════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source_link TEXT NOT NULL,
            thumbnail TEXT DEFAULT '',
            stream_link TEXT DEFAULT '',
            stream_expiry REAL DEFAULT 0,
            source_type TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def db_query(query, params=(), fetch_one=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(query, params)
    if query.strip().upper().startswith("SELECT"):
        result = c.fetchone() if fetch_one else c.fetchall()
        conn.close()
        return result
    conn.commit()
    conn.close()

# ═══════════════ YOUTUBE EXTRACTOR ═══════════════
def extract_youtube(url):
    video_id = None
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        video_id = parsed.path.lstrip("/").split("?")[0]
    elif "youtube.com" in parsed.netloc:
        if "watch" in parsed.path:
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif "shorts" in parsed.path:
            video_id = parsed.path.split("/")[-1]
    
    if not video_id or len(video_id) != 11:
        return {"url": url, "expiry": time.time() + 300, "source": "yt_invalid"}
    
    expiry = time.time() + LINK_CACHE_DURATION
    
    # Invidious
    for instance in ["https://inv.nadeko.net", "https://vid.puffyan.us", "https://invidious.flokinet.to"]:
        try:
            resp = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                for f in data.get("formatStreams", []) + data.get("adaptiveFormats", []):
                    if f.get("url") and "mp4" in (f.get("container", "") or f.get("type", "")):
                        return {"url": f["url"], "expiry": expiry, "source": "invidious"}
        except: continue
    
    # Piped
    for instance in ["https://pipedapi.kavin.rocks", "https://pipedapi.tokhmi.xyz"]:
        try:
            resp = requests.get(f"{instance}/streams/{video_id}", timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                for s in resp.json().get("videoStreams", []):
                    if s.get("url"):
                        return {"url": s["url"], "expiry": expiry, "source": "piped"}
        except: continue
    
    return {"url": f"/proxy-stream/{video_id}", "expiry": expiry, "source": "proxy"}

# ═══════════════ PINTEREST EXTRACTOR ═══════════════
def extract_pinterest(url):
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        html = resp.text
        match = re.search(r'<script[^>]*data-test-id="video-snippet"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            if data.get("contentUrl"):
                return {"url": data["contentUrl"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin"}
        match = re.search(r'"videoBaseUrl"\s*:\s*"([^"]+)"', html)
        if match:
            return {"url": match.group(1).replace("\\/", "/"), "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_base"}
    except: pass
    return {"url": url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_fallback"}

def extract_stream_url(source_url):
    domain = urlparse(source_url).netloc.lower()
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        return extract_youtube(source_url)
    elif "pinterest" in domain or "pin.it" in domain:
        return extract_pinterest(source_url)
    elif source_url.endswith(".mp4"):
        return {"url": source_url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "direct"}
    else:
        return {"url": source_url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "generic"}

# ═══════════════ ROUTES ═══════════════
@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "app": "Sumit x mods v4.0",
        "id_format": "10-char random (e.g. a7b3k9m2x1)"
    })

@app.route("/api/videos")
def get_videos():
    videos = db_query("SELECT id, title, thumbnail, source_link, source_type, created_at FROM videos ORDER BY created_at DESC")
    return jsonify([dict(v) for v in videos])

@app.route("/api/add-video", methods=["POST"])
def add_video():
    data = request.get_json()
    title = data.get("title", "").strip()
    source_link = data.get("source_link", "").strip()
    thumbnail = data.get("thumbnail", "").strip()
    
    if not title or not source_link:
        return jsonify({"error": "Title and Source Link required"}), 400
    
    vid = generate_id()
    while db_query("SELECT id FROM videos WHERE id = ?", (vid,), fetch_one=True):
        vid = generate_id()
    
    domain = urlparse(source_link).netloc.lower()
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        source_type = "youtube"
    elif "pinterest" in domain or "pin.it" in domain:
        source_type = "pinterest"
    elif source_link.endswith(".mp4"):
        source_type = "direct_mp4"
    else:
        source_type = "other"
    
    db_query(
        "INSERT INTO videos (id, title, source_link, thumbnail, source_type) VALUES (?, ?, ?, ?, ?)",
        (vid, title, source_link, thumbnail, source_type)
    )
    return jsonify({"success": True, "video_id": vid})

@app.route("/api/delete-video/<video_id>", methods=["DELETE"])
def delete_video(video_id):
    db_query("DELETE FROM videos WHERE id = ?", (video_id,))
    return jsonify({"success": True})

@app.route("/api/update-video/<video_id>", methods=["PUT"])
def update_video(video_id):
    data = request.get_json()
    updates = []
    params = []
    if data.get("title"):
        updates.append("title = ?"); params.append(data["title"])
    if data.get("source_link"):
        updates.append("source_link = ?"); params.append(data["source_link"])
        updates.append("stream_link = ''"); updates.append("stream_expiry = 0")
    if data.get("thumbnail"):
        updates.append("thumbnail = ?"); params.append(data["thumbnail"])
    if not updates:
        return jsonify({"error": "No fields"}), 400
    params.append(video_id)
    db_query(f"UPDATE videos SET {', '.join(updates)} WHERE id = ?", params)
    return jsonify({"success": True})

@app.route("/get-stream-link/<video_id>")
def get_stream_link(video_id):
    video = db_query("SELECT * FROM videos WHERE id = ?", (video_id,), fetch_one=True)
    if not video:
        return jsonify({"error": "Video not found"}), 404
    
    now = time.time()
    if video["stream_link"] and video["stream_expiry"] > now:
        return jsonify({
            "success": True,
            "stream_url": video["stream_link"],
            "title": video["title"],
            "thumbnail": video["thumbnail"],
            "cached": True,
            "expires_at": datetime.fromtimestamp(video["stream_expiry"]).isoformat(),
            "source": video["source_type"]
        })
    
    result = extract_stream_url(video["source_link"])
    stream_url = result.get("url", video["source_link"])
    expiry = result.get("expiry", now + LINK_CACHE_DURATION)
    
    db_query(
        "UPDATE videos SET stream_link = ?, stream_expiry = ? WHERE id = ?",
        (stream_url, expiry, video_id)
    )
    
    return jsonify({
        "success": True,
        "stream_url": stream_url,
        "title": video["title"],
        "thumbnail": video["thumbnail"],
        "cached": False,
        "expires_at": datetime.fromtimestamp(expiry).isoformat(),
        "source": result.get("source", "unknown")
    })

@app.route("/api/stream-stats")
def stream_stats():
    total = db_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)["count"]
    return jsonify({"total_videos": total})

@app.route("/proxy-stream/<video_id>")
def proxy_stream(video_id):
    try:
        import yt_dlp
        ydl_opts = {
            "format": "best[ext=mp4]/best[height<=720]",
            "quiet": True, "no_warnings": True,
            "geo_bypass": True, "noplaylist": True,
            "socket_timeout": 20,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            video_url = info.get("url", "")
            if video_url:
                def generate():
                    with requests.get(video_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.youtube.com/"}, stream=True, timeout=30) as r:
                        if r.status_code == 200:
                            for chunk in r.iter_content(chunk_size=8192):
                                yield chunk
                return Response(
                    generate(), status=200, mimetype="video/mp4",
                    headers={"Content-Disposition": "inline", "Cache-Control": "no-cache", "Access-Control-Allow-Origin": "*"}
                )
    except: pass
    return jsonify({"error": "Proxy stream failed"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Sumit x mods v4.0 :{port}")
    app.run(host="0.0.0.0", port=port, debug=False)