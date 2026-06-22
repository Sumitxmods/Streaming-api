#!/usr/bin/env python3
"""
💣 SUMIT X MODS — ATOMIC BOMB v6.1 [YT FIXED]
- YouTube: 🔥 Spoof Pool + 4 Fallback Methods
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

# ═══════════════ 🔥 SPOOF POOL ═══════════════
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

# ═══════════════ 🔥 YOUTUBE — FIXED (4 Methods) ═══════════════
def extract_youtube(url):
    """YouTube: yt-dlp → Invidious → Piped → ytdown.to"""
    video_id = None
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        video_id = parsed.path.lstrip("/").split("?")[0]
    elif "youtube.com" in parsed.netloc:
        if "watch" in parsed.path: video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif "shorts" in parsed.path: video_id = parsed.path.split("/")[-1]

    if not video_id or len(video_id) != 11:
        return None

    print(f"[YT] Extracting: {video_id}")
    selected = random.choice(SPOOF_POOL)
    expiry = time.time() + LINK_CACHE_DURATION

    # ═══════ METHOD 1: yt-dlp with Spoof Headers ═══════
    try:
        import yt_dlp
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'quiet': True, 'no_warnings': True, 'skip_download': True,
            'geo_bypass': True, 'noplaylist': True, 'socket_timeout': 25,
            'http_headers': {
                'User-Agent': selected["ua"],
                'X-Forwarded-For': selected["ip"],
                'Client-IP': selected["ip"],
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9'
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info and info.get('formats'):
                progressive = [f for f in info['formats']
                             if f.get('url') and f.get('vcodec') != 'none' and f.get('acodec') != 'none']
                if progressive:
                    print(f"[YT] ✅ yt-dlp progressive")
                    return {"url": progressive[-1]['url'], "expiry": expiry, "source": "yt_spoof"}
                
                mp4s = [f for f in info['formats'] if f.get('url') and f.get('ext') == 'mp4']
                if mp4s:
                    print(f"[YT] ✅ yt-dlp mp4")
                    return {"url": mp4s[-1]['url'], "expiry": expiry, "source": "yt_spoof"}
                
                for f in info['formats']:
                    if f.get('url'):
                        print(f"[YT] ✅ yt-dlp any")
                        return {"url": f['url'], "expiry": expiry, "source": "yt_spoof"}
            
            if info.get('url'):
                print(f"[YT] ✅ yt-dlp direct")
                return {"url": info['url'], "expiry": expiry, "source": "yt_direct"}
    except Exception as e:
        print(f"[YT] yt-dlp: {str(e)[:60]}")

    # ═══════ METHOD 2: Invidious API ═══════
    for instance in ["https://inv.nadeko.net", "https://vid.puffyan.us", "https://invidious.flokinet.to", "https://yt.artemislena.eu"]:
        try:
            resp = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=10,
                headers={"User-Agent": selected["ua"]})
            if resp.status_code == 200:
                data = resp.json()
                for f in data.get("formatStreams", []) + data.get("adaptiveFormats", []):
                    if f.get("url") and "mp4" in (f.get("container", "") or f.get("type", "")):
                        print(f"[YT] ✅ Invidious")
                        return {"url": f["url"], "expiry": expiry, "source": "invidious"}
        except: continue

    # ═══════ METHOD 3: Piped API ═══════
    for instance in ["https://pipedapi.kavin.rocks", "https://pipedapi.tokhmi.xyz"]:
        try:
            resp = requests.get(f"{instance}/streams/{video_id}", timeout=10,
                headers={"User-Agent": selected["ua"]})
            if resp.status_code == 200:
                for s in resp.json().get("videoStreams", []):
                    if s.get("url"):
                        print(f"[YT] ✅ Piped")
                        return {"url": s["url"], "expiry": expiry, "source": "piped"}
        except: continue

    # ═══════ METHOD 4: ytdown.to ═══════
    try:
        r = requests.post("https://app.ytdown.to/proxy.php",
            data={"url": f"https://www.youtube.com/watch?v={video_id}"},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": selected["ua"],
                "Origin": "https://app.ytdown.to",
                "Referer": "https://app.ytdown.to/"
            }, timeout=20)
        d = r.json()
        if d.get("links"):
            best = None
            for l in d["links"]:
                if "720" in l.get("quality", ""): best = l; break
            if not best: best = d["links"][0]
            if best and best.get("url"):
                print(f"[YT] ✅ ytdown.to")
                return {"url": best["url"], "expiry": expiry, "source": "ytdown"}
    except: pass

    print(f"[YT] ❌ ALL FAILED: {video_id}")
    return None

# ═══════════════ 📌 PINTEREST ═══════════════
def extract_pinterest(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        html = resp.text
        
        match = re.search(r'<script[^>]*data-test-id="video-snippet"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            if data.get("contentUrl"):
                return {"url": data["contentUrl"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin"}
        
        match = re.search(r'"videoBaseUrl"\s*:\s*"([^"]+)"', html)
        if match:
            return {"url": match.group(1).replace("\\/", "/"), "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_base"}
        
        match = re.search(r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"', html)
        if match:
            return {"url": match.group(1).replace("\\/", "/"), "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_url"}
        
        match = re.search(r'<video[^>]+src\s*=\s*["\']([^"\']+)["\']', html)
        if match:
            return {"url": match.group(1), "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_tag"}
    except: pass
    return {"url": url, "expiry": time.time() + 300, "source": "pin_fallback"}

# ═══════════════ 📸 INSTAGRAM ═══════════════
def extract_instagram(url):
    try:
        import yt_dlp
        selected = random.choice(SPOOF_POOL)
        ydl_opts = {
            "format": "best[ext=mp4]/best", "quiet": True, "no_warnings": True,
            "geo_bypass": True, "noplaylist": True, "socket_timeout": 15,
            "http_headers": {'User-Agent': selected["ua"], 'X-Forwarded-For': selected["ip"]}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("url"):
                return {"url": info["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "instagram"}
            for f in info.get("formats", []):
                if f.get("url") and f.get("ext") in ("mp4", "m3u8"):
                    return {"url": f["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "instagram"}
    except: pass
    return None

# ═══════════════ 🌐 GENERIC ═══════════════
def extract_generic(url):
    try:
        import yt_dlp
        selected = random.choice(SPOOF_POOL)
        ydl_opts = {
            "format": "best[ext=mp4]/best", "quiet": True, "no_warnings": True,
            "geo_bypass": True, "noplaylist": True,
            "http_headers": {'User-Agent': selected["ua"], 'X-Forwarded-For': selected["ip"]}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("url"):
                return {"url": info["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "generic"}
    except: pass
    if url.endswith(".mp4"):
        return {"url": url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "direct"}
    return None

# ═══════════════ MAIN EXTRACTOR ═══════════════
def extract_fresh(original_url):
    domain = urlparse(original_url).netloc.lower()
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        return extract_youtube(original_url)
    elif "pinterest" in domain or "pin.it" in domain:
        return extract_pinterest(original_url)
    elif "instagram" in domain:
        return extract_instagram(original_url)
    else:
        return extract_generic(original_url) or {
            "url": original_url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "fallback"
        }

# ═══════════════ ROUTES ═══════════════
@app.route("/")
def home():
    return jsonify({
        "status": "💣 Atomic Bomb v6.1 [YT FIXED]",
        "app": "Sumit x mods",
        "youtube": "🔥 Spoof + 4 Fallbacks",
        "pinterest": "📌 Old Method",
        "instagram": "📸 Old Method"
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
    st = "youtube" if any(x in domain for x in ["youtube.com","youtu.be"]) else \
         "pinterest" if "pinterest" in domain or "pin.it" in domain else \
         "instagram" if "instagram" in domain else \
         "direct_mp4" if original_url.endswith(".mp4") else "other"

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
            "cached": True, "expires_at": datetime.fromtimestamp(video["stream_expiry"]).isoformat()
        })

    original = video.get("original_url", video.get("source_link", ""))
    print(f"[💣] EXPIRED: {vid}")

    result = extract_fresh(original)
    if not result: return jsonify({"error": "Extraction failed", "success": False}), 500

    stream_url = result["url"]
    expiry = result.get("expiry", now + LINK_CACHE_DURATION)

    db_query("UPDATE videos SET stream_url=?, stream_expiry=? WHERE id=?", (stream_url, expiry, vid))
    fb_update(f"videos/{vid}", {"stream_url": stream_url, "stream_expiry": expiry})

    print(f"[💣] FRESH: {vid}")
    return jsonify({
        "success": True, "stream_url": stream_url,
        "title": video.get("title", ""), "thumbnail": video.get("thumbnail", ""),
        "cached": False, "expires_at": datetime.fromtimestamp(expiry).isoformat(),
        "source": result.get("source", "unknown")
    })

@app.route("/api/stream-stats")
def stats():
    t = db_query("SELECT COUNT(*) as c FROM videos", fetch_one=True)
    a = db_query("SELECT COUNT(*) as c FROM videos WHERE stream_expiry > ?", (time.time(),), fetch_one=True)
    return jsonify({"total": t["c"] if t else 0, "active": a["c"] if a else 0})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"💣 v6.1 YT FIXED :{port}")
    app.run(host="0.0.0.0", port=port, debug=False)