#!/usr/bin/env python3
"""
💣 SUMIT X MODS — ATOMIC BOMB BACKEND
- Firebase + SQLite dual storage
- Auto-refresh on click
- original_url FOREVER, stream_url UPDATES
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
LINK_CACHE_DURATION = 1800  # 30 min

# ═══════════════ FIREBASE ═══════════════
FIREBASE_URL = "https://videohostvip-default-rtdb.firebaseio.com"
FIREBASE_SECRET = ""  # Optional — public DB ke liye nahi chahiye

def fb_get(path):
    try:
        r = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=5)
        return r.json()
    except:
        return None

def fb_set(path, data):
    try:
        requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=5)
    except:
        pass

def fb_update(path, data):
    try:
        requests.patch(f"{FIREBASE_URL}/{path}.json", json=data, timeout=5)
    except:
        pass

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
        r = c.fetchone(); conn.close(); return r
    if fetch_all:
        r = c.fetchall(); conn.close(); return r
    conn.commit(); conn.close()

# ═══════════════ EXTRACTORS ═══════════════
def extract_youtube(url):
    vid = None
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        vid = parsed.path.lstrip("/").split("?")[0]
    elif "youtube.com" in parsed.netloc:
        if "watch" in parsed.path: vid = parse_qs(parsed.query).get("v", [None])[0]
        elif "shorts" in parsed.path: vid = parsed.path.split("/")[-1]
    if not vid or len(vid) != 11: return None

    # ytdown.to
    try:
        r = requests.post("https://app.ytdown.to/proxy.php",
            data={"url": f"https://www.youtube.com/watch?v={vid}"},
            headers={"Content-Type":"application/x-www-form-urlencoded","User-Agent":"Mozilla/5.0","Origin":"https://app.ytdown.to","Referer":"https://app.ytdown.to/"},
            timeout=15)
        d = r.json()
        if d.get("links"):
            best = d["links"][0]
            for l in d["links"]:
                if "720" in l.get("quality",""): best = l; break
            return {"url": best["url"], "expiry": time.time()+LINK_CACHE_DURATION, "source": "ytdown"}
    except: pass

    # Invidious
    for ins in ["https://inv.nadeko.net","https://vid.puffyan.us"]:
        try:
            r = requests.get(f"{ins}/api/v1/videos/{vid}", timeout=8)
            if r.status_code==200:
                for f in r.json().get("formatStreams",[]):
                    if f.get("url"): return {"url":f["url"],"expiry":time.time()+LINK_CACHE_DURATION,"source":"invidious"}
        except: continue
    return None

def extract_pinterest(url):
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        h = r.text
        m = re.search(r'<script[^>]*data-test-id="video-snippet"[^>]*>(.*?)</script>', h, re.DOTALL)
        if m:
            d = json.loads(m.group(1))
            if d.get("contentUrl"): return {"url":d["contentUrl"],"expiry":time.time()+LINK_CACHE_DURATION,"source":"pin"}
        m = re.search(r'"videoBaseUrl"\s*:\s*"([^"]+)"', h)
        if m: return {"url":m.group(1).replace("\\/","/"),"expiry":time.time()+LINK_CACHE_DURATION,"source":"pin"}
    except: pass
    return None

def extract_generic(url):
    try:
        import yt_dlp
        ydl = {"format":"best[ext=mp4]/best","quiet":True,"no_warnings":True,"geo_bypass":True,"noplaylist":True}
        with yt_dlp.YoutubeDL(ydl) as y: info = y.extract_info(url, download=False)
        if info.get("url"): return {"url":info["url"],"expiry":time.time()+LINK_CACHE_DURATION,"source":"generic"}
    except: pass
    if url.endswith(".mp4"): return {"url":url,"expiry":time.time()+LINK_CACHE_DURATION,"source":"direct"}
    return None

def extract_fresh(original_url):
    domain = urlparse(original_url).netloc.lower()
    if any(x in domain for x in ["youtube.com","youtu.be"]): return extract_youtube(original_url)
    elif "pinterest" in domain or "pin.it" in domain: return extract_pinterest(original_url)
    else: return extract_generic(original_url) or {"url":original_url,"expiry":time.time()+LINK_CACHE_DURATION,"source":"fallback"}

# ═══════════════ SYNC FIREBASE ← SQLITE ═══════════════
def sync_to_firebase(video_id, data):
    fb_update(f"videos/{video_id}", data)

# ═══════════════ ROUTES ═══════════════
@app.route("/")
def home():
    return jsonify({"status":"💣 Atomic Bomb Backend","app":"Sumit x mods"})

@app.route("/api/videos")
def get_videos():
    vids = db_query("SELECT * FROM videos ORDER BY created_at DESC", fetch_all=True)
    return jsonify([dict(v) for v in (vids or [])])

@app.route("/api/add-video", methods=["POST"])
def add_video():
    d = request.get_json()
    title = d.get("title","").strip()
    original_url = d.get("source_link","").strip()
    thumbnail = d.get("thumbnail","").strip()
    if not title or not original_url: return jsonify({"error":"Required"}), 400

    vid = generate_id()
    while db_query("SELECT id FROM videos WHERE id=?",(vid,),fetch_one=True): vid = generate_id()

    domain = urlparse(original_url).netloc.lower()
    st = "youtube" if any(x in domain for x in ["youtube.com","youtu.be"]) else "pinterest" if "pinterest" in domain or "pin.it" in domain else "direct"

    db_query("INSERT INTO videos(id,title,original_url,thumbnail,source_type) VALUES(?,?,?,?,?)",(vid,title,original_url,thumbnail,st))
    
    # Firebase sync
    fb_set(f"videos/{vid}",{"id":vid,"title":title,"original_url":original_url,"thumbnail":thumbnail,"source_type":st,"created_at":datetime.now().isoformat()})

    return jsonify({"success":True,"video_id":vid})

@app.route("/api/delete-video/<vid>", methods=["DELETE"])
def delete_video(vid):
    db_query("DELETE FROM videos WHERE id=?",(vid,))
    requests.delete(f"{FIREBASE_URL}/videos/{vid}.json")
    return jsonify({"success":True})

@app.route("/api/update-video/<vid>", methods=["PUT"])
def update_video(vid):
    d = request.get_json()
    if d.get("source_link"):
        db_query("UPDATE videos SET original_url=?, stream_url='', stream_expiry=0 WHERE id=?",(d["source_link"],vid))
        fb_update(f"videos/{vid}",{"original_url":d["source_link"],"stream_url":"","stream_expiry":0})
    return jsonify({"success":True})

# ═══════════════ 💣 CORE — ATOMIC STREAM ═══════════════
@app.route("/get-stream-link/<vid>")
def get_stream_link(vid):
    now = time.time()
    
    # 1. DB check
    video = db_query("SELECT * FROM videos WHERE id=?",(vid,),fetch_one=True)
    if not video:
        # Firebase fallback
        fb_data = fb_get(f"videos/{vid}")
        if not fb_data: return jsonify({"error":"Not found","success":False}),404
        video = fb_data
    
    video = dict(video)
    
    # 2. Valid stream? → RETURN
    if video.get("stream_url") and video.get("stream_expiry",0) > now:
        return jsonify({"success":True,"stream_url":video["stream_url"],"title":video.get("title",""),"thumbnail":video.get("thumbnail",""),"cached":True,"expires_at":datetime.fromtimestamp(video["stream_expiry"]).isoformat()})
    
    # 3. Expired → FRESH EXTRACTION
    original = video.get("original_url", video.get("source_link", ""))
    print(f"[💣] EXPIRED: {vid} → Extracting from: {original[:50]}...")
    
    result = extract_fresh(original)
    if not result:
        return jsonify({"error":"Extraction failed","success":False}),500
    
    stream_url = result["url"]
    expiry = result.get("expiry", now+LINK_CACHE_DURATION)
    
    # 4. UPDATE DB + FIREBASE
    db_query("UPDATE videos SET stream_url=?, stream_expiry=? WHERE id=?",(stream_url, expiry, vid))
    fb_update(f"videos/{vid}",{"stream_url":stream_url,"stream_expiry":expiry})
    
    print(f"[💣] FRESH: {vid} → {stream_url[:60]}...")
    
    return jsonify({"success":True,"stream_url":stream_url,"title":video.get("title",""),"thumbnail":video.get("thumbnail",""),"cached":False,"expires_at":datetime.fromtimestamp(expiry).isoformat(),"source":result.get("source","unknown")})

@app.route("/api/stream-stats")
def stats():
    t = db_query("SELECT COUNT(*) as c FROM videos",fetch_one=True)
    a = db_query("SELECT COUNT(*) as c FROM videos WHERE stream_expiry > ?",(time.time(),),fetch_one=True)
    return jsonify({"total":t["c"]if t else 0,"active":a["c"]if a else 0})

if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    print(f"💣 Atomic Bomb on :{port}")
    app.run(host="0.0.0.0",port=port,debug=False)