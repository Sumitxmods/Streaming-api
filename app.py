#!/usr/bin/env python3
"""
Sumit x mods - Video Stream v4.1 [ALL FIXED]
- YouTube ✅ (Invidious + Piped + InnerTube)
- Pinterest ✅, Instagram ✅, Facebook ✅, Direct ✅
- Random 10-char IDs
- Per-IP stream links with expiry
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
LINK_CACHE_DURATION = 3600  # 1 hour
IP_CACHE = {}  # IP-based cache: {ip: {video_id: {url, expiry}}}

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
            source_type TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # IP-based stream cache table
    c.execute("""
        CREATE TABLE IF NOT EXISTS ip_streams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            ip_address TEXT,
            stream_url TEXT,
            expiry REAL,
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

# ═══════════════ YOUTUBE EXTRACTOR (FIXED) ═══════════════
def extract_youtube(url):
    """Extract YouTube video URL using Invidious + Piped + InnerTube"""
    video_id = None
    parsed = urlparse(url)
    
    if "youtu.be" in parsed.netloc:
        video_id = parsed.path.lstrip("/").split("?")[0]
    elif "youtube.com" in parsed.netloc:
        if "watch" in parsed.path:
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif "embed" in parsed.path:
            video_id = parsed.path.split("/")[-1]
        elif "shorts" in parsed.path:
            video_id = parsed.path.split("/")[-1]
    
    if not video_id or len(video_id) != 11:
        print(f"[YT] Invalid ID: {video_id}")
        return None
    
    print(f"[YT] Extracting: {video_id}")
    expiry = time.time() + LINK_CACHE_DURATION
    
    # Method 1: Invidious API
    invidious_instances = [
        "https://inv.nadeko.net",
        "https://vid.puffyan.us", 
        "https://invidious.flokinet.to",
        "https://yt.artemislena.eu",
        "https://invidious.privacyredirect.com",
    ]
    
    for instance in invidious_instances:
        try:
            api_url = f"{instance}/api/v1/videos/{video_id}"
            resp = requests.get(api_url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            })
            if resp.status_code == 200:
                data = resp.json()
                all_formats = data.get("formatStreams", []) + data.get("adaptiveFormats", [])
                
                # Find best MP4
                best = None
                for f in all_formats:
                    container = f.get("container", "") or f.get("type", "")
                    if "mp4" in container:
                        quality = f.get("quality", "") or f.get("resolution", "")
                        if "720" in quality:
                            best = f
                            break
                        if best is None:
                            best = f
                
                if best and best.get("url"):
                    print(f"[YT] ✅ Invidious: {instance}")
                    return {"url": best["url"], "expiry": expiry, "source": "invidious"}
                
                # Fallback: any URL
                for f in all_formats:
                    if f.get("url"):
                        print(f"[YT] ✅ Invidious fallback")
                        return {"url": f["url"], "expiry": expiry, "source": "invidious"}
        except Exception as e:
            continue
    
    # Method 2: Piped API
    piped_instances = [
        "https://pipedapi.kavin.rocks",
        "https://pipedapi.tokhmi.xyz",
    ]
    
    for instance in piped_instances:
        try:
            api_url = f"{instance}/streams/{video_id}"
            resp = requests.get(api_url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0"
            })
            if resp.status_code == 200:
                data = resp.json()
                video_streams = data.get("videoStreams", [])
                
                best = None
                for s in video_streams:
                    if s.get("quality") == "720p" and s.get("url"):
                        best = s
                        break
                if best is None:
                    for s in video_streams:
                        if s.get("url"):
                            best = s
                            break
                
                if best and best.get("url"):
                    print(f"[YT] ✅ Piped: {instance}")
                    return {"url": best["url"], "expiry": expiry, "source": "piped"}
        except Exception as e:
            continue
    
    # Method 3: InnerTube API (YouTube Android)
    try:
        api_key = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        headers = {
            "User-Agent": "com.google.android.youtube/19.09.37 (Linux; U; Android 13; Pixel 6) gzip",
            "Content-Type": "application/json",
            "X-YouTube-Client-Name": "3",
            "X-YouTube-Client-Version": "19.09.37",
        }
        payload = {
            "videoId": video_id,
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "19.09.37",
                    "androidSdkVersion": 33,
                    "deviceModel": "Pixel 6",
                    "osName": "Android",
                    "osVersion": "13",
                }
            },
            "contentCheckOk": True,
            "racyCheckOk": True,
        }
        resp = requests.post(
            f"https://www.youtube.com/youtubei/v1/player?key={api_key}",
            json=payload, headers=headers, timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            streaming_data = data.get("streamingData", {})
            all_formats = streaming_data.get("formats", []) + streaming_data.get("adaptiveFormats", [])
            
            for f in all_formats:
                mime = f.get("mimeType", "")
                if "video/mp4" in mime and f.get("url"):
                    print(f"[YT] ✅ InnerTube")
                    return {"url": f["url"], "expiry": expiry, "source": "innertube"}
            
            # SignatureCipher fallback
            for f in all_formats:
                if f.get("signatureCipher"):
                    cipher_params = parse_qs(f["signatureCipher"])
                    if cipher_params.get("url"):
                        cipher_url = cipher_params["url"][0]
                        if cipher_params.get("s"):
                            sp = cipher_params.get("sp", ["sig"])[0]
                            cipher_url += f"&{sp}={cipher_params['s'][0]}"
                        print(f"[YT] ✅ InnerTube cipher")
                        return {"url": cipher_url, "expiry": expiry, "source": "innertube_cipher"}
    except Exception as e:
        print(f"[YT] InnerTube error: {e}")
    
    print(f"[YT] ❌ All methods failed for {video_id}")
    return None

# ═══════════════ PINTEREST EXTRACTOR ═══════════════
def extract_pinterest(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        html = resp.text
        
        # Method 1: video-snippet
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
        
        # Method 3: Any .mp4 URL
        match = re.search(r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"', html)
        if match:
            vurl = match.group(1).replace("\\u002F", "/").replace("\\/", "/")
            return {"url": vurl, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_url"}
        
        # Method 4: video tag
        match = re.search(r'<video[^>]+src\s*=\s*["\']([^"\']+)["\']', html)
        if match:
            return {"url": match.group(1), "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_tag"}
            
    except Exception as e:
        print(f"[Pin] Error: {e}")
    
    return {"url": url, "expiry": time.time() + 300, "source": "pin_fallback"}

# ═══════════════ GENERIC EXTRACTOR ═══════════════
def extract_generic(url):
    """For Instagram, Facebook, Twitter etc."""
    try:
        # Try yt-dlp for generic
        import yt_dlp
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True, "no_warnings": True,
            "geo_bypass": True, "noplaylist": True,
            "socket_timeout": 15,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("url"):
                return {"url": info["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "generic"}
            for f in info.get("formats", []):
                if f.get("url") and f.get("ext") in ("mp4", "m3u8"):
                    return {"url": f["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "generic"}
    except:
        pass
    
    # Direct URL if .mp4
    if url.endswith(".mp4"):
        return {"url": url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "direct"}
    
    return {"url": url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "generic_fallback"}

# ═══════════════ MAIN EXTRACTOR ═══════════════
def extract_stream_url(source_url, ip_address):
    """Extract stream URL with per-IP caching"""
    domain = urlparse(source_url).netloc.lower()
    
    # Check IP cache first
    cache_key = f"{ip_address}_{source_url}"
    if ip_address in IP_CACHE:
        ip_data = IP_CACHE[ip_address]
        for vid, data in ip_data.items():
            if data.get("source_url") == source_url and data.get("expiry", 0) > time.time():
                print(f"[Cache] Using IP-cached stream for {ip_address}")
                return data.get("result")
    
    # Extract based on platform
    result = None
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        result = extract_youtube(source_url)
    elif "pinterest" in domain or "pin.it" in domain:
        result = extract_pinterest(source_url)
    elif any(x in domain for x in ["instagram.com", "facebook.com", "fb.watch", "twitter.com", "x.com"]):
        result = extract_generic(source_url)
    elif source_url.endswith((".mp4", ".m3u8")):
        result = {"url": source_url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "direct"}
    else:
        result = extract_generic(source_url)
    
    # Cache per IP
    if result and ip_address:
        if ip_address not in IP_CACHE:
            IP_CACHE[ip_address] = {}
        IP_CACHE[ip_address][source_url] = {
            "result": result,
            "source_url": source_url,
            "expiry": result.get("expiry", time.time() + LINK_CACHE_DURATION)
        }
    
    return result

# ═══════════════ ROUTES ═══════════════
@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "app": "Sumit x mods v4.1",
        "features": ["Random IDs", "Per-IP cache", "YouTube ✅", "Pinterest ✅", "All ✅"]
    })

@app.route("/api/videos")
def get_videos():
    videos = db_query(
        "SELECT id, title, thumbnail, source_link, source_type, created_at FROM videos ORDER BY created_at DESC",
        fetch_all=True
    )
    return jsonify([dict(v) for v in (videos or [])])

@app.route("/api/add-video", methods=["POST"])
def add_video():
    data = request.get_json()
    title = data.get("title", "").strip()
    source_link = data.get("source_link", "").strip()
    thumbnail = data.get("thumbnail", "").strip()
    
    if not title or not source_link:
        return jsonify({"error": "Title and Source Link required"}), 400
    
    # Generate unique random ID
    vid = generate_id()
    attempts = 0
    while db_query("SELECT id FROM videos WHERE id = ?", (vid,), fetch_one=True) and attempts < 10:
        vid = generate_id()
        attempts += 1
    
    domain = urlparse(source_link).netloc.lower()
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        source_type = "youtube"
    elif "pinterest" in domain or "pin.it" in domain:
        source_type = "pinterest"
    elif "instagram" in domain:
        source_type = "instagram"
    elif "facebook" in domain or "fb.watch" in domain:
        source_type = "facebook"
    elif source_link.endswith(".mp4"):
        source_type = "direct_mp4"
    else:
        source_type = "other"
    
    db_query(
        "INSERT INTO videos (id, title, source_link, thumbnail, source_type) VALUES (?, ?, ?, ?, ?)",
        (vid, title, source_link, thumbnail, source_type)
    )
    
    print(f"[Add] New video: {vid} - {title}")
    return jsonify({"success": True, "video_id": vid})

@app.route("/api/delete-video/<video_id>", methods=["DELETE"])
def delete_video(video_id):
    db_query("DELETE FROM videos WHERE id = ?", (video_id,))
    db_query("DELETE FROM ip_streams WHERE video_id = ?", (video_id,))
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
        # Clear IP cache for this video
        for ip in IP_CACHE:
            IP_CACHE[ip].pop(video_id, None)
        db_query("DELETE FROM ip_streams WHERE video_id = ?", (video_id,))
    if data.get("thumbnail"):
        updates.append("thumbnail = ?"); params.append(data["thumbnail"])
    if not updates:
        return jsonify({"error": "No fields"}), 400
    params.append(video_id)
    db_query(f"UPDATE videos SET {', '.join(updates)} WHERE id = ?", params)
    return jsonify({"success": True})

@app.route("/get-stream-link/<video_id>")
def get_stream_link(video_id):
    """Get stream link - per IP with expiry"""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "0.0.0.0"
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    video = db_query("SELECT * FROM videos WHERE id = ?", (video_id,), fetch_one=True)
    if not video:
        return jsonify({"error": "Video not found", "success": False}), 404
    
    video = dict(video)
    now = time.time()
    
    # Check IP-based cache in database
    cached = db_query(
        "SELECT * FROM ip_streams WHERE video_id = ? AND ip_address = ? AND expiry > ? ORDER BY created_at DESC LIMIT 1",
        (video_id, client_ip, now),
        fetch_one=True
    )
    
    if cached:
        cached = dict(cached)
        print(f"[Stream] IP-cached: {video_id} for {client_ip}")
        return jsonify({
            "success": True,
            "stream_url": cached["stream_url"],
            "title": video["title"],
            "thumbnail": video["thumbnail"],
            "cached": True,
            "expires_at": datetime.fromtimestamp(cached["expiry"]).isoformat(),
            "ip": client_ip,
            "source": video["source_type"]
        })
    
    # Extract new stream URL for this IP
    print(f"[Stream] New extraction: {video_id} ({video['source_type']}) for IP: {client_ip}")
    
    result = extract_stream_url(video["source_link"], client_ip)
    
    if not result:
        return jsonify({
            "success": False,
            "error": "Failed to extract stream URL. Platform may be blocked.",
            "title": video["title"]
        }), 500
    
    stream_url = result.get("url", video["source_link"])
    expiry = result.get("expiry", now + LINK_CACHE_DURATION)
    
    # Save to IP cache database
    db_query(
        "INSERT INTO ip_streams (video_id, ip_address, stream_url, expiry) VALUES (?, ?, ?, ?)",
        (video_id, client_ip, stream_url, expiry)
    )
    
    print(f"[Stream] Success: {video_id} → {stream_url[:60]}...")
    
    return jsonify({
        "success": True,
        "stream_url": stream_url,
        "title": video["title"],
        "thumbnail": video["thumbnail"],
        "cached": False,
        "expires_at": datetime.fromtimestamp(expiry).isoformat(),
        "ip": client_ip,
        "source": result.get("source", "unknown")
    })

@app.route("/api/stream-stats")
def stream_stats():
    total = db_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)
    total = total["count"] if total else 0
    cached = db_query("SELECT COUNT(*) as count FROM ip_streams WHERE expiry > ?", (time.time(),), fetch_one=True)
    cached = cached["count"] if cached else 0
    return jsonify({"total_videos": total, "active_streams": cached})

@app.route("/api/health")
def health():
    return jsonify({"status": "healthy", "ip_cache_size": len(IP_CACHE)})

@app.route("/proxy-stream/<video_id>")
def proxy_stream(video_id):
    """Proxy for YouTube IP-locked streams"""
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
                    with requests.get(video_url, headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://www.youtube.com/"
                    }, stream=True, timeout=30) as r:
                        if r.status_code == 200:
                            for chunk in r.iter_content(chunk_size=8192):
                                yield chunk
                return Response(
                    generate(), status=200, mimetype="video/mp4",
                    headers={
                        "Content-Disposition": "inline",
                        "Cache-Control": "no-cache",
                        "Access-Control-Allow-Origin": "*"
                    }
                )
    except Exception as e:
        print(f"[Proxy] Error: {e}")
    
    return jsonify({"error": "Proxy stream failed"}), 500

# ═══════════════ START ═══════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
╔══════════════════════════════════════════╗
║   Sumit x mods v4.1 [ALL FIXED]         ║
║   YouTube ✅ | Pinterest ✅ | All ✅     ║
║   Random IDs | Per-IP Cache             ║
║   Port: {port}                             ║
╚══════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=False)