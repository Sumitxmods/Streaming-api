#!/usr/bin/env python3
"""
🎬 SUMIT X MODS — STREAM API
Render Ready | Firebase | Working
"""

import os, json, time, hashlib, requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

FIREBASE_URL = "https://file-share-sumit-default-rtdb.firebaseio.com"

def fb_get(path):
    try:
        resp = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except: return None

def fb_post(path, data):
    try:
        resp = requests.post(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)
        return resp.json() if resp.status_code == 200 else {}
    except: return {}

def fb_put(path, data):
    try:
        requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)
        return True
    except: return False

def fb_delete(path):
    try:
        requests.delete(f"{FIREBASE_URL}/{path}.json", timeout=10)
        return True
    except: return False

@app.route("/")
def home():
    return jsonify({"status": "ok", "name": "SUMIT X MODS API"})

@app.route("/api/videos")
def get_videos():
    data = fb_get("videos") or {}
    videos = []
    for k, v in data.items():
        v["id"] = k
        videos.append(v)
    videos.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify(videos)

@app.route("/api/add", methods=["POST"])
def add_video():
    try:
        data = request.get_json()
        title = (data.get("title") or "").strip()
        link = (data.get("link") or "").strip()
        thumb = (data.get("thumbnail") or "").strip()
        
        if not title or not link:
            return jsonify({"success": False, "error": "Title and link required"})
        
        link_lower = link.lower()
        if "youtube.com" in link_lower or "youtu.be" in link_lower:
            stype = "youtube"
        elif "pinterest.com" in link_lower or "pin.it" in link_lower:
            stype = "pinterest"
        elif any(link_lower.endswith(e) for e in [".mp4", ".m3u8", ".webm", ".mkv", ".avi"]):
            stype = "direct"
        else:
            stype = "other"
        
        video = {
            "title": title,
            "link": link,
            "thumbnail": thumb or "https://i.pinimg.com/236x/31/07/62/31076221c206aee22474343a955c7515.jpg",
            "type": stype,
            "created_at": datetime.now().isoformat(),
            "views": 0
        }
        
        result = fb_post("videos", video)
        vid = result.get("name", str(int(time.time())))
        
        return jsonify({"success": True, "video_id": vid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/delete/<vid>", methods=["DELETE"])
def del_video(vid):
    fb_delete(f"videos/{vid}")
    return jsonify({"success": True})

@app.route("/api/stream/<vid>")
def stream(vid):
    video = fb_get(f"videos/{vid}")
    if not video:
        return jsonify({"success": False, "error": "Not found"})
    
    link = video.get("link", "")
    video["views"] = video.get("views", 0) + 1
    fb_put(f"videos/{vid}", video)
    
    # Generate stream URL
    stream_url = link
    if "youtube.com" in link or "youtu.be" in link:
        import re
        match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', link)
        if match:
            stream_url = f"https://www.youtube.com/embed/{match.group(1)}"
    
    return jsonify({
        "success": True,
        "stream_url": stream_url,
        "title": video["title"],
        "type": video.get("type", "other"),
        "thumbnail": video.get("thumbnail", ""),
        "share_url": f"{request.host_url}share.html?id={vid}",
        "download_url": stream_url
    })

@app.route("/api/stats")
def stats():
    data = fb_get("videos") or {}
    views = sum(v.get("views", 0) for v in data.values())
    return jsonify({"total_videos": len(data), "total_views": views})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🎬 API Running on port {port}")
    app.run(host="0.0.0.0", port=port)