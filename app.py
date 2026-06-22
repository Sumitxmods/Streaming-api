#!/usr/bin/env python3
"""
Sumit x mods - Video Stream v5.0 [ARCHITECTURE FIXED]
- Original URL → Stream URL (with expiry)
- Every 5 min: Auto-refresh expiring streams
- User open: Check → Expired? → Fresh → Return
- YouTube via ytdown.to API
"""

import os, re, json, time, sqlite3, secrets, string, threading
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.secret_key = os.urandom(24).hex()

DB_PATH = "database.db"
LINK_CACHE_DURATION = 1800  # 30 minutes
AUTO_REFRESH_BEFORE = 300   # Refresh 5 min before expiry

# ═══════════════ RANDOM ID ═══════════════
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
            original_url TEXT NOT NULL,
            thumbnail TEXT DEFAULT '',
            stream_url TEXT DEFAULT '',
            stream_expiry REAL DEFAULT 0,
            source_type TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def db_query(query, params=(), fetch_one=False, fetch_all=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(query, params)
    if fetch_one:
        result = c.fetchone()
        conn.close()
        return result
    if fetch_all:
        result = c.fetchall()
        conn.close()
        return result
    conn.commit()
    conn.close()

# ═══════════════ YOUTUBE EXTRACTION (ytdown.to) ═══════════════
def extract_youtube(url):
    """YouTube via ytdown.to API"""
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
        return None

    expiry = time.time() + LINK_CACHE_DURATION
    print(f"[YT] ytdown: {video_id}")

    try:
        # ytdown.to API
        resp = requests.post(
            "https://app.ytdown.to/proxy.php",
            data={"url": f"https://www.youtube.com/watch?v={video_id}"},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://app.ytdown.to",
                "Referer": "https://app.ytdown.to/"
            },
            timeout=20
        )
        data = resp.json()
        
        if data.get("links"):
            best = None
            for link in data["links"]:
                q = link.get("quality", "")
                if "720" in q:
                    best = link
                    break
                if best is None:
                    best = link
            
            if best and best.get("url"):
                return {
                    "url": best["url"],
                    "expiry": expiry,
                    "source": "ytdown"
                }
    except Exception as e:
        print(f"[YT] ytdown error: {e}")

    # Fallback: Invidious
    return extract_invidious(video_id, expiry)

def extract_invidious(video_id, expiry):
    for instance in ["https://inv.nadeko.net", "https://vid.puffyan.us", "https://invidious.flokinet.to"]:
        try:
            resp = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for f in data.get("formatStreams", []) + data.get("adaptiveFormats", []):
                    if f.get("url") and "mp4" in (f.get("container", "") or ""):
                        return {"url": f["url"], "expiry": expiry, "source": "invidious"}
        except:
            continue
    return None

# ═══════════════ PINTEREST ═══════════════
def extract_pinterest(url):
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        html = resp.text
        match = re.search(r'<script[^>]*data-test-id="video-snippet"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            if data.get("contentUrl"):
                return {"url": data["contentUrl"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin"}
        match = re.search(r'"videoBaseUrl"\s*:\s*"([^"]+)"', html)
        if match:
            return {"url": match.group(1).replace("\\/", "/"), "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_base"}
    except:
        pass
    return None

# ═══════════════ GENERIC (Instagram/Facebook) ═══════════════
def extract_generic(url):
    try:
        import yt_dlp
        ydl_opts = {"format": "best[ext=mp4]/best", "quiet": True, "no_warnings": True, "geo_bypass": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("url"):
                return {"url": info["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "generic"}
    except:
        pass
    if url.endswith(".mp4"):
        return {"url": url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "direct"}
    return None

# ═══════════════ MAIN EXTRACTOR ═══════════════
def extract_fresh_stream(source_url):
    """Original URL se fresh stream URL nikalo"""
    domain = urlparse(source_url).netloc.lower()
    
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        return extract_youtube(source_url)
    elif "pinterest" in domain or "pin.it" in domain:
        return extract_pinterest(source_url)
    else:
        return extract_generic(source_url) or {
            "url": source_url,
            "expiry": time.time() + LINK_CACHE_DURATION,
            "source": "fallback"
        }

# ═══════════════ AUTO-REFRESH BACKGROUND ═══════════════
def auto_refresh_loop():
    """Every 5 min: refresh streams about to expire"""
    while True:
        time.sleep(300)  # 5 minutes
        try:
            now = time.time()
            threshold = now + AUTO_REFRESH_BEFORE
            
            # Find videos with streams expiring soon
            videos = db_query(
                "SELECT id, original_url FROM videos WHERE stream_expiry > 0 AND stream_expiry < ?",
                (threshold,),
                fetch_all=True
            )
            
            if videos:
                print(f"[AutoRefresh] Refreshing {len(videos)} expiring streams...")
                for v in videos:
                    v = dict(v)
                    result = extract_fresh_stream(v["original_url"])
                    if result and result.get("url"):
                        db_query(
                            "UPDATE videos SET stream_url = ?, stream_expiry = ? WHERE id = ?",
                            (result["url"], result["expiry"], v["id"])
                        )
                        print(f"[AutoRefresh] ✅ {v['id']}")
        except Exception as e:
            print(f"[AutoRefresh] Error: {e}")

# Start background thread
threading.Thread(target=auto_refresh_loop, daemon=True).start()

# ═══════════════ ROUTES ═══════════════
@app.route("/")
def home():
    return jsonify({"status": "online", "app": "Sumit x mods v5.0", "auto_refresh": "5 min"})

@app.route("/api/videos")
def get_videos():
    videos = db_query("SELECT id, title, thumbnail, original_url, source_type, stream_expiry, created_at FROM videos ORDER BY created_at DESC", fetch_all=True)
    return jsonify([dict(v) for v in (videos or [])])

@app.route("/api/add-video", methods=["POST"])
def add_video():
    data = request.get_json()
    title = data.get("title", "").strip()
    original_url = data.get("source_link", "").strip()
    thumbnail = data.get("thumbnail", "").strip()
    
    if not title or not original_url:
        return jsonify({"error": "Required"}), 400
    
    vid = generate_id()
    while db_query("SELECT id FROM videos WHERE id = ?", (vid,), fetch_one=True):
        vid = generate_id()
    
    domain = urlparse(original_url).netloc.lower()
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        st = "youtube"
    elif "pinterest" in domain or "pin.it" in domain:
        st = "pinterest"
    elif original_url.endswith(".mp4"):
        st = "direct_mp4"
    else:
        st = "other"
    
    db_query(
        "INSERT INTO videos (id, title, original_url, thumbnail, source_type) VALUES (?,?,?,?,?)",
        (vid, title, original_url, thumbnail, st)
    )
    return jsonify({"success": True, "video_id": vid})

@app.route("/api/delete-video/<vid>", methods=["DELETE"])
def delete_video(vid):
    db_query("DELETE FROM videos WHERE id = ?", (vid,))
    return jsonify({"success": True})

@app.route("/api/update-video/<vid>", methods=["PUT"])
def update_video(vid):
    data = request.get_json()
    if data.get("source_link"):
        db_query("UPDATE videos SET original_url = ?, stream_url = '', stream_expiry = 0 WHERE id = ?",
                 (data["source_link"], vid))
    return jsonify({"success": True})

@app.route("/get-stream-link/<vid>")
def get_stream_link(vid):
    """
    ═══════════════ CORE LOGIC ═══════════════
    1. Database se video lo
    2. Agar stream_url valid hai → return karo
    3. Agar expire ho gaya → original_url se fresh nikalo → update DB → return
    """
    video = db_query("SELECT * FROM videos WHERE id = ?", (vid,), fetch_one=True)
    if not video:
        return jsonify({"error": "Not found", "success": False}), 404
    
    video = dict(video)
    now = time.time()
    
    # ✅ VALID STREAM — return immediately
    if video["stream_url"] and video["stream_expiry"] > now:
        return jsonify({
            "success": True,
            "stream_url": video["stream_url"],
            "title": video["title"],
            "thumbnail": video["thumbnail"],
            "cached": True,
            "expires_at": datetime.fromtimestamp(video["stream_expiry"]).isoformat(),
            "source": video["source_type"]
        })
    
    # ✅ EXPIRED — fresh stream from original URL
    print(f"[Stream] Expired — refreshing: {vid}")
    result = extract_fresh_stream(video["original_url"])
    
    if result and result.get("url"):
        stream_url = result["url"]
        expiry = result.get("expiry", now + LINK_CACHE_DURATION)
        
        db_query(
            "UPDATE videos SET stream_url = ?, stream_expiry = ? WHERE id = ?",
            (stream_url, expiry, vid)
        )
        
        print(f"[Stream] ✅ Fresh: {vid}")
        return jsonify({
            "success": True,
            "stream_url": stream_url,
            "title": video["title"],
            "thumbnail": video["thumbnail"],
            "cached": False,
            "expires_at": datetime.fromtimestamp(expiry).isoformat(),
            "source": result.get("source", "unknown")
        })
    
    return jsonify({"error": "Failed to extract", "success": False}), 500

@app.route("/api/stream-stats")
def stream_stats():
    total = db_query("SELECT COUNT(*) as c FROM videos", fetch_one=True)
    active = db_query("SELECT COUNT(*) as c FROM videos WHERE stream_expiry > ?", (time.time(),), fetch_one=True)
    return jsonify({
        "total_videos": total["c"] if total else 0,
        "active_streams": active["c"] if active else 0
    })

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Sumit x mods v5.0 :{port}")
    app.run(host="0.0.0.0", port=port, debug=False)