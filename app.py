#!/usr/bin/env python3
"""
💣 SUMIT X MODS — ATOMIC BOMB v6.0
- YouTube: 🔥 INTEGRATED VIDSSAVE LIVE API ROUTE (FIXED)
- Pinterest: Old method (video-snippet, videoBaseUrl)
- Instagram: Old method (yt-dlp generic)
- Facebook, Direct MP4: Old method
- Firebase + SQLite dual storage
- Auto-refresh on click
"""

import os, re, json, time, sqlite3, secrets, string, random, threading
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.secret_key = os.urandom(24).hex()

DB_PATH = "database.db"
LINK_CACHE_DURATION = 1800  # 30 min

# ═══════════════ FIREBASE ═══════════════
FIREBASE_URL = "https://videohostvip-default-rtdb.firebaseio.com"

def fb_get(path):
    try:
        r = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=5)
        return r.json()
    except: return None

def fb_set(path, data):
    try: requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=5)
    except: pass

def fb_update(path, data):
    try: requests.patch(f"{FIREBASE_URL}/{path}.json", json=data, timeout=5)
    except: pass

# ═══════════════ 🔥 SPOOF POOL — YOUTUBE SPECIAL ═══════════════
SPOOF_POOL = [
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "ip": "203.0.113.42"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15", "ip": "198.51.100.89"},
    {"ua": "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36", "ip": "192.0.2.115"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0", "ip": "103.241.12.67"},
    {"ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/605.1.15", "ip": "185.220.101.5"},
    {"ua": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36", "ip": "45.33.32.156"},
    {"ua": "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1", "ip": "64.62.156.88"},
]

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
    if fetch_one: r = c.fetchone(); conn.close(); return r
    if fetch_all: r = c.fetchall(); conn.close(); return r
    conn.commit(); conn.close()

# ═══════════════ 🔥 YOUTUBE — DYNAMIC API ROUTE INTEGRATED ═══════════════
def extract_youtube(url):
    """YouTube using the vidssave API layout from your analysis"""
    video_id = None
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        video_id = parsed.path.lstrip("/").split("?")[0]
    elif "youtube.com" in parsed.netloc:
        if "watch" in parsed.path: video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif "shorts" in parsed.path: video_id = parsed.path.split("/")[-1]

    if not video_id or len(video_id) != 11:
        return None

    print(f"[YT-API] Dispatching payload for video: {video_id}")
    selected = random.choice(SPOOF_POOL)
    expiry = time.time() + LINK_CACHE_DURATION

    # EXACT API LAYOUT FROM YOUR SCREENSHOTS
    api_url = "https://api.vidssave.com/api/contentsite_api/media/parse"
    payload = {
        "auth": "20250901msjmlqp",
        "domain": "api-ak.vidssave.com",
        "origin": "source",
        "link": f"https://www.youtube.com/watch?v={video_id}"
    }
    headers = {
        "authority": "api.vidssave.com",
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://vidssave.com",
        "referer": "https://vidssave.com/",
        "user-agent": selected["ua"]
    }

    try:
        response = requests.post(api_url, headers=headers, data=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            inner_data = data.get('data', {})
            formats = inner_data.get('formats', []) or inner_data.get('download_list', [])
            
            stream_url = ""
            if formats and len(formats) > 0:
                stream_url = formats[0].get('url') or formats[0].get('link')
            else:
                stream_url = inner_data.get('url') or inner_data.get('link')

            if stream_url:
                print(f"[YT-API] ✅ Success Extraction via Live Node")
                return {"url": stream_url, "expiry": expiry, "source": "vidssave_api"}
    except Exception as e:
        print(f"[YT-API] Route failed, switching to backup: {e}")

    # Fallback: ytdown.to
    try:
        r = requests.post("https://app.ytdown.to/proxy.php",
            data={"url": f"https://www.youtube.com/watch?v={video_id}"},
            headers={"Content-Type":"application/x-www-form-urlencoded","User-Agent":selected["ua"],"Origin":"https://app.ytdown.to","Referer":"https://app.ytdown.to/"},
            timeout=15)
        d = r.json()
        if d.get("links"):
            best = d["links"][0]
            for l in d["links"]:
                if "720" in l.get("quality",""): best = l; break
            return {"url": best["url"], "expiry": expiry, "source": "ytdown"}
    except: pass

    return None

# ═══════════════ 📌 PINTEREST — OLD METHOD (SAME) ═══════════════
def extract_pinterest(url):
    """Pinterest — old method: video-snippet + videoBaseUrl"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        html = resp.text
        
        # Method 1: video-snippet JSON
        match = re.search(r'<script[^>]*data-test-id="video-snippet"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            if data.get("contentUrl"):
                return {"url": data["contentUrl"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin"}
        
        # Method 2: videoBaseUrl
        match = re.search(r'"videoBaseUrl"\s*:\s*"([^"]+)"', html)
        if match:
            vurl = match.group(1).replace("\\u002F", "/").replace("\\/", "/")
            return {"url": vurl, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_base"}
        
        # Method 3: Any .mp4 in JSON
        match = re.search(r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"', html)
        if match:
            vurl = match.group(1).replace("\\u002F", "/").replace("\\/", "/")
            return {"url": vurl, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_url"}
        
        # Method 4: video tag src
        match = re.search(r'<video[^>]+src\s*=\s*["\']([^"\']+)["\']', html)
        if match:
            return {"url": match.group(1), "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_tag"}
            
    except Exception as e:
        print(f"[PIN] Error: {e}")
    
    return {"url": url, "expiry": time.time() + 300, "source": "pin_fallback"}

# ═══════════════ 📸 INSTAGRAM — OLD METHOD (yt-dlp) ═══════════════
def extract_instagram(url):
    """Instagram — old method: yt-dlp generic"""
    try:
        import yt_dlp
        selected = random.choice(SPOOF_POOL)
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True, "no_warnings": True,
            "geo_bypass": True, "noplaylist": True,
            "socket_timeout": 15,
            "http_headers": {
                'User-Agent': selected["ua"],
                'X-Forwarded-For': selected["ip"]
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("url"):
                return {"url": info["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "instagram"}
            for f in info.get("formats", []):
                if f.get("url") and f.get("ext") in ("mp4", "m3u8"):
                    return {"url": f["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "instagram"}
    except Exception as e:
        print(f"[INSTA] Error: {e}")
    return None

# ═══════════════ 🌐 GENERIC — OLD METHOD ═══════════════
def extract_generic(url):
    """Generic: Facebook, Twitter, Direct MP4"""
    try:
        import yt_dlp
        selected = random.choice(SPOOF_POOL)
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True, "no_warnings": True,
            "geo_bypass": True, "noplaylist": True,
            "http_headers": {
                'User-Agent': selected["ua"],
                'X-Forwarded-For': selected["ip"]
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("url"):
                return {"url": info["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "generic"}
            for f in info.get("formats", []):
                if f.get("url") and f.get("ext") in ("mp4", "m3u8"):
                    return {"url": f["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "generic"}
    except: pass
    if url.endswith(".mp4"):
        return {"url": url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "direct"}
    return None

# ═══════════════ MAIN EXTRACTOR ═══════════════
def extract_fresh(original_url):
    domain = urlparse(original_url).netloc.lower()
    
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        return extract_youtube(original_url)  # 🔥 FIXED LIVE API GATEWAY
    elif "pinterest" in domain or "pin.it" in domain:
        return extract_pinterest(original_url)  # 📌 OLD METHOD
    elif "instagram" in domain:
        return extract_instagram(original_url)  # 📸 OLD METHOD
    else:
        return extract_generic(original_url) or {
            "url": original_url,
            "expiry": time.time() + LINK_CACHE_DURATION,
            "source": "fallback"
        }

# ═══════════════ ROUTES ═══════════════
@app.route("/")
def home():
    return jsonify({
        "status": "💣 Atomic Bomb v6.0",
        "app": "Sumit x mods",
        "youtube": "🔥 Live Vidssave API Patched",
        "pinterest": "📌 Old Method",
        "instagram": "📸 Old Method",
        "spoof_nodes": len(SPOOF_POOL)
    })

@app.route("/api/videos")
def get_videos():
    vids = db_query("SELECT * FROM videos ORDER BY created_at DESC", fetch_all=True)
    return jsonify([dict(v) for v in (vids or [])])

@app.route("/api/add-video", methods=["POST"])
def add_video():
    d = request.get_json()
    title = d.get("title", "").strip()
    original_url = d.get("source_link", "").strip()
    thumbnail = d.get("thumbnail", "").strip()
    if not title or not original_url: return jsonify({"error": "Required"}), 400

    vid = generate_id()
    while db_query("SELECT id FROM videos WHERE id=?", (vid,), fetch_one=True): vid = generate_id()

    domain = urlparse(original_url).netloc.lower()
    if any(x in domain for x in ["youtube.com", "youtu.be"]): st = "youtube"
    elif "pinterest" in domain or "pin.it" in domain: st = "pinterest"
    elif "instagram" in domain: st = "instagram"
    elif original_url.endswith(".mp4"): st = "direct_mp4"
    else: st = "other"

    db_query("INSERT INTO videos(id,title,original_url,thumbnail,source_type) VALUES(?,?,?,?,?)",
             (vid, title, original_url, thumbnail, st))
    fb_set(f"videos/{vid}", {"id": vid, "title": title, "original_url": original_url,
           "thumbnail": thumbnail, "source_type": st, "created_at": datetime.now().isoformat()})

    return jsonify({"success": True, "video_id": vid})

@app.route("/api/delete-video/<vid>", methods=["DELETE"])
def delete_video(vid):
    db_query("DELETE FROM videos WHERE id=?", (vid,))
    requests.delete(f"{FIREBASE_URL}/videos/{vid}.json")
    return jsonify({"success": True})

@app.route("/api/update-video/<vid>", methods=["PUT"])
def update_video(vid):
    d = request.get_json()
    if d.get("source_link"):
        db_query("UPDATE videos SET original_url=?, stream_url='', stream_expiry=0 WHERE id=?",
                 (d["source_link"], vid))
        fb_update(f"videos/{vid}", {"original_url": d["source_link"], "stream_url": "", "stream_expiry": 0})
    return jsonify({"success": True})

# ═══════════════ 💣 CORE STREAM ═══════════════
@app.route("/get-stream-link/<vid>")
def get_stream_link(vid):
    now = time.time()
    video = db_query("SELECT * FROM videos WHERE id=?", (vid,), fetch_one=True)
    if not video:
        fb_data = fb_get(f"videos/{vid}")
        if not fb_data: return jsonify({"error": "Not found", "success": False}), 404
        video = fb_data
    video = dict(video)

    if video.get("stream_url") and video.get("stream_expiry", 0) > now:
        return jsonify({
            "success": True, "stream_url": video["stream_url"],
            "title": video.get("title", ""), "thumbnail": video.get("thumbnail", ""),
            "cached": True,
            "expires_at": datetime.fromtimestamp(video["stream_expiry"]).isoformat()
        })

    original = video.get("original_url", video.get("source_link", ""))
    print(f"[💣] EXPIRED: {vid} → {original[:50]}...")

    result = extract_fresh(original)
    if not result: return jsonify({"error": "Extraction failed", "success": False}), 500

    stream_url = result["url"]
    expiry = result.get("expiry", now + LINK_CACHE_DURATION)

    db_query("UPDATE videos SET stream_url=?, stream_expiry=? WHERE id=?", (stream_url, expiry, vid))
    fb_update(f"videos/{vid}", {"stream_url": stream_url, "stream_expiry": expiry})

    print(f"[💣] FRESH: {vid} → {stream_url[:60]}...")
    return jsonify({
        "success": True, "stream_url": stream_url,
        "title": video.get("title", ""), "thumbnail": video.get("thumbnail", ""),
        "cached": False,
        "expires_at": datetime.fromtimestamp(expiry).isoformat(),
        "source": result.get("source", "unknown")
    })

@app.route("/api/stream-stats")
def stats():
    t = db_query("SELECT COUNT(*) as c FROM videos", fetch_one=True)
    a = db_query("SELECT COUNT(*) as c FROM videos WHERE stream_expiry > ?", (time.time(),), fetch_one=True)
    return jsonify({"total": t["c"] if t else 0, "active": a["c"] if a else 0})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
╔══════════════════════════════════════════╗
║   💣 SUMIT X MODS — ATOMIC BOMB v6.0   ║
║   🔥 YT: Patched Vidssave API Route    ║
║   📌 Pin: Old Method                   ║
║   📸 Insta: Old Method                 ║
║   🚀 Port: {port}                       ║
╚══════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=False)