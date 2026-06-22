#!/usr/bin/env python3
"""
💣 SUMIT X MODS — MULTI-PLATFORM AUTO-REFRESH ENGINE v8.0
- Special Focus: YouTube Universal Playback Stream Bypass (No IP-Lock)
- Platforms: YouTube, Instagram, Facebook, Pinterest
- Checker: Live HTTP Status Verification before response
"""

import os, re, json, time, sqlite3, secrets, string, random
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DB_PATH = "database.db"
LINK_CACHE_DURATION = 1200  # 20 Mins safe boundary for hot-links
FIREBASE_URL = "https://videohostvip-default-rtdb.firebaseio.com"

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
]

def fb_update(path, data):
    try: requests.patch(f"{FIREBASE_URL}/{path}.json", json=data, timeout=5)
    except: pass

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, original_url TEXT NOT NULL,
            thumbnail TEXT DEFAULT '', stream_url TEXT DEFAULT '', stream_expiry REAL DEFAULT 0,
            source_type TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

# 🎥 ADVANCED YOUTUBE EXTRACTOR (Bypasses 403 IP Lock)
def extract_youtube(url):
    video_id = None
    if "youtu.be" in url: 
        video_id = url.split("/")[-1].split("?")[0]
    elif "youtube.com" in url:
        if "watch" in url: video_id = parse_qs(urlparse(url).query).get("v", [None])[0]
        elif "shorts" in url: video_id = url.split("/shorts/")[-1].split("?")[0]
    
    if not video_id: return None
    
    # Target Primary API Gateway (Cobalt/Vidssave cluster fallback)
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": random.choice(UA_POOL)
    }
    
    # Method 1: Cobalt Engine Protocol for absolute client streaming redirection
    try:
        cobalt_payload = {
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "videoQuality": "720",
            "audioFormat": "mp3",
            "downloadMode": "video",
            "youtubeHLS": True # Generates adaptive streaming profile
        }
        res = requests.post("https://api.cobalt.tools/", headers=headers, json=cobalt_payload, timeout=10)
        if res.status_code == 200:
            stream_url = res.json().get("url")
            if stream_url: return stream_url
    except: pass

    # Method 2: Vidssave Cluster API Bypass
    try:
        vs_payload = {"auth": "20250901msjmlqp", "domain": "api-ak.vidssave.com", "origin": "source", "link": f"https://www.youtube.com/watch?v={video_id}"}
        vs_headers = {"origin": "https://vidssave.com", "referer": "https://vidssave.com/", "user-agent": random.choice(UA_POOL)}
        r = requests.post("https://api.vidssave.com/api/contentsite_api/media/parse", headers=vs_headers, data=vs_payload, timeout=10)
        if r.status_code == 200:
            d = r.json().get('data', {})
            formats = d.get('formats', []) or d.get('download_list', [])
            stream = formats[0].get('url') or formats[0].get('link') if formats else (d.get('url') or d.get('link'))
            if stream: return stream
    except: pass

    return f"https://www.youtube.com/embed/{video_id}" # Direct iframe embed if stream mapping fails

# 📱 INSTAGRAM / FACEBOOK / PINTEREST EXTRACTOR ROUTER
def extract_social_media(url):
    headers = {"user-agent": random.choice(UA_POOL), "origin": "https://vidssave.com"}
    payload = {"auth": "20250901msjmlqp", "domain": "api-ak.vidssave.com", "origin": "source", "link": url}
    try:
        r = requests.post("https://api.vidssave.com/api/contentsite_api/media/parse", headers=headers, data=payload, timeout=12)
        if r.status_code == 200:
            d = r.json().get('data', {})
            formats = d.get('formats', []) or d.get('download_list', [])
            stream = formats[0].get('url') or formats[0].get('link') if formats else (d.get('url') or d.get('link'))
            if stream: return stream
    except: pass
    return url

def get_fresh_stream(url):
    url_l = url.lower()
    if "youtu" in url_l: 
        return extract_youtube(url)
    return extract_social_media(url)

# 🔍 STABILITY CHECKER (Ensures link isn't dead/expired)
def is_link_alive(stream_url):
    if not stream_url or "youtube.com/embed" in stream_url: 
        return True # Standard fallback routes require no HTTP validation
    try:
        # Standard fast ping via HEAD request
        res = requests.head(stream_url, headers={"User-Agent": random.choice(UA_POOL)}, allow_redirects=True, timeout=4)
        if res.status_code in [200, 206]: return True
        if res.status_code in [403, 404, 410]: return False
        
        # Cross-validation fallback using GET byte-range stream check
        res_get = requests.get(stream_url, headers={"User-Agent": random.choice(UA_POOL)}, stream=True, timeout=4)
        return res_get.status_code in [200, 206]
    except: 
        return False

# ═══════════════ API INTERFACES ═══════════════
@app.route("/api/videos")
def get_videos():
    vids = db_query("SELECT * FROM videos ORDER BY created_at DESC", fetch_all=True)
    return jsonify([dict(v) for v in (vids or [])])

@app.route("/api/add-video", methods=["POST"])
def add_video():
    d = request.get_json() or {}
    title = d.get("title", "").strip()
    original_url = d.get("source_link", "").strip()
    thumbnail = d.get("thumbnail", "").strip()
    if not title or not original_url: return jsonify({"error": "Data Missing"}), 400

    vid = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10))
    url_l = original_url.lower()
    st = "youtube" if "youtu" in url_l else "instagram" if "insta" in url_l else "facebook" if "face" in url_l or "fb" in url_l else "pinterest" if "pin" in url_l else "direct"

    db_query("INSERT INTO videos(id,title,original_url,thumbnail,source_type) VALUES(?,?,?,?,?)", (vid, title, original_url, thumbnail, st))
    
    # Store directly to Firebase RTDB
    requests.put(f"{FIREBASE_URL}/videos/{vid}.json", json={"id": vid, "title": title, "original_url": original_url, "source_link": original_url, "thumbnail": thumbnail, "source_type": st, "created_at": datetime.now().isoformat()})
    return jsonify({"success": True, "video_id": vid})

# 🔥 INTERCEPT ENGINE: Ran on every request by Admin or User
@app.route("/get-stream-link/<vid>")
def get_stream_link(vid):
    video = db_query("SELECT * FROM videos WHERE id=?", (vid,), fetch_one=True)
    if not video: return jsonify({"error": "Video Registry Missing"}), 404
    video = dict(video)

    current_stream = video.get("stream_url")
    original_link = video.get("original_url")
    now = time.time()

    # 1. Check if token timestamp is valid AND link responds with active streaming bytes
    if current_stream and video.get("stream_expiry", 0) > now:
        if is_link_live(current_stream):
            return jsonify({"success": True, "stream_url": current_stream, "title": video["title"], "type": video["source_type"]})

    # 2. Re-extraction triggers instantly if link is dead or timestamp is up
    fresh_url = get_fresh_stream(original_link)
    if not fresh_url: fresh_url = original_link # Safeguard backup

    new_expiry = now + LINK_CACHE_DURATION
    db_query("UPDATE videos SET stream_url=?, stream_expiry=? WHERE id=?", (fresh_url, new_expiry, vid))
    fb_update(f"videos/{vid}", {"stream_url": fresh_url, "stream_expiry": new_expiry})

    return jsonify({"success": True, "stream_url": fresh_url, "title": video["title"], "type": video["source_type"]})

@app.route("/api/delete-video/<vid>", methods=["DELETE"])
def delete_video(vid):
    db_query("DELETE FROM videos WHERE id=?", (vid,))
    requests.delete(f"{FIREBASE_URL}/videos/{vid}.json")
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))