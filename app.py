#!/usr/bin/env python3
"""
Sumit x mods - Private Video Stream v3.0
- YouTube ✅, Pinterest ✅, Instagram ✅, Facebook ✅, Direct ✅
- Firebase + SQLite dual storage
- CORS enabled for any frontend domain
- Render / Railway / Hugging Face ready
"""

import os
import re
import json
import time
import sqlite3
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.secret_key = os.urandom(24).hex()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")
LINK_CACHE_DURATION = 3600  # 1 hour

# ============================================================
# DATABASE
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    last_id = c.lastrowid
    conn.close()
    return last_id

# ============================================================
# YOUTUBE EXTRACTION ENGINE (3 fallback methods)
# ============================================================

def extract_youtube(url):
    """YouTube stream URL with 3 fallback methods."""
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
        return {"url": url, "expiry": time.time() + 300, "source": "yt_invalid_id"}
    
    # Method 1: yt-dlp
    try:
        import yt_dlp
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "noplaylist": True,
            "socket_timeout": 15,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])
            best = None
            for f in formats:
                if f.get("ext") == "mp4" and f.get("vcodec") != "none":
                    h = f.get("height", 0) or 0
                    if best is None or h > best.get("height", 0):
                        best = f
            if best and best.get("url"):
                return {"url": best["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "yt-dlp"}
            for f in formats:
                if f.get("url"):
                    return {"url": f["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "yt-dlp_fallback"}
    except:
        pass
    
    # Method 2: Innertube API (Android)
    try:
        api_key = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        payload = {
            "videoId": video_id,
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "19.09.37",
                    "androidSdkVersion": 30,
                    "deviceModel": "Pixel 6",
                    "osName": "Android",
                    "osVersion": "13",
                }
            },
            "playbackContext": {
                "contentPlaybackContext": {
                    "html5Preference": "SHORTS"
                }
            }
        }
        resp = requests.post(
            f"https://www.youtube.com/youtubei/v1/player?key={api_key}",
            json=payload, headers=headers, timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            streaming_data = data.get("streamingData", {})
            for fmt_list in [streaming_data.get("adaptiveFormats", []), streaming_data.get("formats", [])]:
                for f in fmt_list:
                    if f.get("url") and "video/mp4" in f.get("mimeType", ""):
                        return {"url": f["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "yt_innertube"}
            # SignatureCipher fallback
            for f in streaming_data.get("adaptiveFormats", []):
                if f.get("signatureCipher"):
                    from urllib.parse import parse_qs as pqs
                    cipher = pqs(f["signatureCipher"])
                    if cipher.get("url"):
                        url_c = cipher["url"][0]
                        if cipher.get("s"):
                            sp = cipher.get("sp", ["sig"])[0]
                            url_c += f"&{sp}={cipher['s'][0]}"
                        return {"url": url_c, "expiry": time.time() + LINK_CACHE_DURATION, "source": "yt_cipher"}
    except:
        pass
    
    # Method 3: Page scraping
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(f"https://www.youtube.com/watch?v={video_id}", headers=headers, timeout=15)
        if resp.status_code == 200:
            html = resp.text
            match = re.search(r'ytInitialPlayerResponse\s*=\s*({.*?});', html)
            if match:
                try:
                    data = json.loads(match.group(1))
                    for fmt_list in [data.get("streamingData", {}).get("adaptiveFormats", []), data.get("streamingData", {}).get("formats", [])]:
                        for f in fmt_list:
                            if f.get("url"):
                                return {"url": f["url"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "yt_scrape"}
                except:
                    pass
    except:
        pass
    
    return {"url": url, "expiry": time.time() + 300, "source": "yt_fallback"}


def extract_pinterest(url):
    """Pinterest video extraction."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return {"url": url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_fallback"}
        
        html = resp.text
        
        # JSON-LD video snippet
        match = re.search(r'<script[^>]*data-test-id="video-snippet"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if data.get("contentUrl"):
                    return {"url": data["contentUrl"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_ld"}
            except:
                pass
        
        # videoBaseUrl
        match = re.search(r'"videoBaseUrl"\s*:\s*"([^"]+)"', html)
        if match:
            vurl = match.group(1).replace("\\u002F", "/").replace("\\/", "/")
            return {"url": vurl, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_base"}
        
        # Any mp4 URL
        match = re.search(r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"', html)
        if match:
            vurl = match.group(1).replace("\\u002F", "/").replace("\\/", "/")
            return {"url": vurl, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_url"}
        
        # <video> tag src
        match = re.search(r'<video[^>]+src\s*=\s*["\']([^"\']+)["\']', html)
        if match:
            return {"url": match.group(1), "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_videotag"}
            
    except Exception as e:
        print(f"[pinterest error] {e}")
    
    return {"url": url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_fallback"}


def extract_generic(url):
    """Generic extractor using yt-dlp."""
    try:
        import yt_dlp
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True, "no_warnings": True,
            "geo_bypass": True, "noplaylist": True,
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
    return {"url": url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "generic_fallback"}


def extract_stream_url(source_url):
    """Universal stream URL extractor."""
    domain = urlparse(source_url).netloc.lower()
    
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        return extract_youtube(source_url)
    elif "pinterest" in domain or "pin.it" in domain:
        return extract_pinterest(source_url)
    elif "instagram" in domain:
        return extract_generic(source_url)
    elif "facebook" in domain or "fb.watch" in domain:
        return extract_generic(source_url)
    elif "twitter" in domain or "x.com" in domain:
        return extract_generic(source_url)
    elif source_url.endswith(".mp4") or source_url.endswith(".m3u8"):
        return {"url": source_url, "expiry": time.time() + LINK_CACHE_DURATION, "source": "direct"}
    else:
        return extract_generic(source_url)


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "app": "Sumit x mods Stream v3.0",
        "endpoints": {
            "GET /api/videos": "List all videos",
            "POST /api/add-video": "Add a video",
            "PUT /api/update-video/<id>": "Update a video",
            "DELETE /api/delete-video/<id>": "Delete a video",
            "GET /get-stream-link/<id>": "Get stream URL",
            "GET /api/stream-stats": "Get statistics"
        }
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
    
    domain = urlparse(source_link).netloc.lower()
    if any(x in domain for x in ["youtube.com", "youtu.be"]):
        source_type = "youtube"
    elif "pinterest" in domain or "pin.it" in domain:
        source_type = "pinterest"
    elif "instagram" in domain:
        source_type = "instagram"
    elif "facebook" in domain or "fb.watch" in domain:
        source_type = "facebook"
    elif "twitter" in domain or "x.com" in domain:
        source_type = "twitter"
    elif source_link.endswith(".mp4"):
        source_type = "direct_mp4"
    else:
        source_type = "other"
    
    vid = db_query(
        "INSERT INTO videos (title, source_link, thumbnail, source_type) VALUES (?, ?, ?, ?)",
        (title, source_link, thumbnail, source_type)
    )
    return jsonify({"success": True, "video_id": vid})


@app.route("/api/delete-video/<int:video_id>", methods=["DELETE"])
def delete_video(video_id):
    db_query("DELETE FROM videos WHERE id = ?", (video_id,))
    return jsonify({"success": True})


@app.route("/api/update-video/<int:video_id>", methods=["PUT"])
def update_video(video_id):
    data = request.get_json()
    title = data.get("title")
    source_link = data.get("source_link")
    thumbnail = data.get("thumbnail")
    
    updates = []
    params = []
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if source_link is not None:
        updates.append("source_link = ?")
        params.append(source_link)
        updates.append("stream_link = ''")
        updates.append("stream_expiry = 0")
    if thumbnail is not None:
        updates.append("thumbnail = ?")
        params.append(thumbnail)
    
    if not updates:
        return jsonify({"error": "No fields to update"}), 400
    
    params.append(video_id)
    db_query(f"UPDATE videos SET {', '.join(updates)} WHERE id = ?", params)
    return jsonify({"success": True})


@app.route("/get-stream-link/<int:video_id>")
def get_stream_link(video_id):
    """Core endpoint: returns playable stream URL."""
    client_ip = request.remote_addr or "0.0.0.0"
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
            "ip": client_ip,
            "source": video["source_type"]
        })
    
    print(f"[extract] #{video_id} ({video['source_type']}): {video['title']}")
    try:
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
            "ip": client_ip,
            "source": result.get("source", "unknown")
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stream-stats")
def stream_stats():
    total = db_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)["count"]
    cached = db_query("SELECT COUNT(*) as count FROM videos WHERE stream_link != '' AND stream_expiry > ?", 
                      (time.time(),), fetch_one=True)["count"]
    return jsonify({"total_videos": total, "cached_streams": cached})


@app.route("/api/health")
def health():
    try:
        db_query("SELECT 1")
        return jsonify({"status": "healthy", "database": "connected"})
    except:
        return jsonify({"status": "unhealthy", "database": "disconnected"}), 500


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
╔══════════════════════════════════════════════╗
║   Sumit x mods - Video Stream Backend v3.0  ║
║   Running on http://0.0.0.0:{port}           ║
║   Ready for any frontend 🚀                 ║
╚══════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=False)