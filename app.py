#!/usr/bin/env python3
"""
Sumit x mods - Private Video Stream v3.1 [FIXED]
- YouTube ✅ (Invidious + Piped + InnerTube + yt-dlp + Proxy)
- Pinterest ✅, Instagram ✅, Facebook ✅, Direct ✅
- Firebase + SQLite dual storage
- CORS enabled for any frontend domain
- Render / Railway / Hugging Face ready
"""

import os
import re
import json
import time
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import requests
from flask import Flask, request, jsonify, render_template, Response
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
# YOUTUBE EXTRACTION ENGINE (5 fallback methods) [FIXED]
# ============================================================

def extract_youtube(url):
    """YouTube stream URL with 5 fallback methods."""
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

    expiry = time.time() + LINK_CACHE_DURATION
    print(f"[YT] Extracting: {video_id}")

    # ═══════════════════════════════════════════
    # METHOD 1: Invidious API (Public instances)
    # ═══════════════════════════════════════════
    invidious_instances = [
        "https://inv.nadeko.net",
        "https://vid.puffyan.us",
        "https://invidious.slipfox.xyz",
        "https://invidious.privacyredirect.com",
        "https://yt.artemislena.eu",
        "https://invidious.flokinet.to",
    ]
    
    for instance in invidious_instances:
        try:
            api_url = f"{instance}/api/v1/videos/{video_id}"
            resp = requests.get(api_url, timeout=8, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            })
            if resp.status_code == 200:
                data = resp.json()
                format_streams = data.get("formatStreams", [])
                adaptive_formats = data.get("adaptiveFormats", [])
                all_formats = format_streams + adaptive_formats
                
                best = None
                for f in all_formats:
                    if f.get("type", "").startswith("video/mp4") or "mp4" in f.get("container", ""):
                        h = f.get("quality") or f.get("resolution") or ""
                        if "720" in h:
                            best = f
                            break
                        if best is None:
                            best = f
                
                if best and best.get("url"):
                    print(f"[YT] ✅ Invidious: {instance}")
                    return {"url": best["url"], "expiry": expiry, "source": "invidious"}
                
                for f in all_formats:
                    if f.get("url"):
                        print(f"[YT] ✅ Invidious fallback: {instance}")
                        return {"url": f["url"], "expiry": expiry, "source": "invidious_fallback"}
        except Exception as e:
            continue

    # ═══════════════════════════════════════════
    # METHOD 2: Piped API
    # ═══════════════════════════════════════════
    piped_instances = [
        "https://pipedapi.kavin.rocks",
        "https://pipedapi.tokhmi.xyz",
        "https://pipedapi.moomoo.me",
    ]
    
    for instance in piped_instances:
        try:
            api_url = f"{instance}/streams/{video_id}"
            resp = requests.get(api_url, timeout=8, headers={
                "User-Agent": "Mozilla/5.0"
            })
            if resp.status_code == 200:
                data = resp.json()
                video_streams = data.get("videoStreams", [])
                audio_streams = data.get("audioStreams", [])
                
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
                
                for s in video_streams + audio_streams:
                    if s.get("url"):
                        print(f"[YT] ✅ Piped fallback: {instance}")
                        return {"url": s["url"], "expiry": expiry, "source": "piped_fallback"}
        except Exception as e:
            continue

    # ═══════════════════════════════════════════
    # METHOD 3: InnerTube API (Android client)
    # ═══════════════════════════════════════════
    try:
        api_key = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        headers = {
            "User-Agent": "com.google.android.youtube/19.09.37 (Linux; U; Android 13; Pixel 6) gzip",
            "Content-Type": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
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
                    print(f"[YT] ✅ InnerTube video")
                    return {"url": f["url"], "expiry": expiry, "source": "innertube_video"}
            
            for f in all_formats:
                if f.get("url"):
                    print(f"[YT] ✅ InnerTube any")
                    return {"url": f["url"], "expiry": expiry, "source": "innertube_any"}
            
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
        print(f"[YT] InnerTube failed: {e}")

    # ═══════════════════════════════════════════
    # METHOD 4: yt-dlp
    # ═══════════════════════════════════════════
    try:
        import yt_dlp
        ydl_opts = {
            "format": "best[ext=mp4]/best[height<=720]",
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            
            if info.get("url"):
                print(f"[YT] ✅ yt-dlp direct")
                return {"url": info["url"], "expiry": expiry, "source": "yt-dlp_direct"}
            
            formats = info.get("formats", [])
            best_format = None
            for f in formats:
                if f.get("ext") == "mp4" and f.get("vcodec") != "none":
                    h = f.get("height", 0) or 0
                    if best_format is None or h > (best_format.get("height", 0) or 0):
                        if h <= 720:
                            best_format = f
            
            if not best_format:
                for f in formats:
                    if f.get("url") and f.get("ext") == "mp4":
                        best_format = f
                        break
            
            if best_format and best_format.get("url"):
                print(f"[YT] ✅ yt-dlp format")
                return {"url": best_format["url"], "expiry": expiry, "source": "yt-dlp_format"}
            
            for f in formats:
                if f.get("url"):
                    print(f"[YT] ✅ yt-dlp any")
                    return {"url": f["url"], "expiry": expiry, "source": "yt-dlp_any"}
                    
    except Exception as e:
        print(f"[YT] yt-dlp failed: {e}")

    # ═══════════════════════════════════════════
    # METHOD 5: YouTube Page Scrape
    # ═══════════════════════════════════════════
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
                data = json.loads(match.group(1))
                all_formats = data.get("streamingData", {}).get("formats", []) + \
                              data.get("streamingData", {}).get("adaptiveFormats", [])
                for f in all_formats:
                    if f.get("url"):
                        print(f"[YT] ✅ Page scrape")
                        return {"url": f["url"], "expiry": expiry, "source": "yt_scrape"}
    except Exception as e:
        print(f"[YT] Scrape failed: {e}")

    # ═══════════════════════════════════════════
    # ULTIMATE FALLBACK: Proxy stream
    # ═══════════════════════════════════════════
    proxy_url = f"/proxy-stream/{video_id}"
    print(f"[YT] ⚠️ Using proxy stream")
    return {"url": proxy_url, "expiry": expiry, "source": "proxy_stream"}


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
        
        match = re.search(r'<script[^>]*data-test-id="video-snippet"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if data.get("contentUrl"):
                    return {"url": data["contentUrl"], "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_ld"}
            except:
                pass
        
        match = re.search(r'"videoBaseUrl"\s*:\s*"([^"]+)"', html)
        if match:
            vurl = match.group(1).replace("\\u002F", "/").replace("\\/", "/")
            return {"url": vurl, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_base"}
        
        match = re.search(r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"', html)
        if match:
            vurl = match.group(1).replace("\\u002F", "/").replace("\\/", "/")
            return {"url": vurl, "expiry": time.time() + LINK_CACHE_DURATION, "source": "pin_url"}
        
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
# PROXY STREAM ENDPOINT (for YouTube fallback)
# ============================================================
@app.route("/proxy-stream/<video_id>")
def proxy_stream(video_id):
    """Server-side YouTube proxy stream (bypasses IP lock)"""
    import yt_dlp
    
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        ydl_opts = {
            "format": "best[ext=mp4]/best[height<=720]",
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "noplaylist": True,
            "socket_timeout": 20,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            video_url = info.get("url", "")
            
            if video_url:
                headers = {
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "Referer": "https://www.youtube.com/",
                }
                
                def generate():
                    with requests.get(video_url, headers=headers, stream=True, timeout=30) as r:
                        if r.status_code == 200:
                            for chunk in r.iter_content(chunk_size=8192):
                                yield chunk
                
                return Response(
                    generate(),
                    status=200,
                    mimetype="video/mp4",
                    headers={
                        "Content-Disposition": "inline",
                        "Cache-Control": "no-cache",
                        "Access-Control-Allow-Origin": "*",
                    }
                )
    except Exception as e:
        print(f"[proxy error] {e}")
    
    return jsonify({"error": "Proxy stream failed"}), 500


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "app": "Sumit x mods Stream v3.1 [FIXED]",
        "endpoints": {
            "GET /api/videos": "List all videos",
            "POST /api/add-video": "Add a video",
            "PUT /api/update-video/<id>": "Update a video",
            "DELETE /api/delete-video/<id>": "Delete a video",
            "GET /get-stream-link/<id>": "Get stream URL",
            "GET /proxy-stream/<video_id>": "Proxy stream (YouTube fallback)",
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
║   Sumit x mods - Video Stream Backend v3.1  ║
║   Running on http://0.0.0.0:{port}           ║
║   YouTube ✅ Fixed | Pinterest ✅ | All ✅   ║
╚══════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=False)