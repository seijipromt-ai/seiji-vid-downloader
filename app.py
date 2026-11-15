#!/usr/bin/env python3
# app.py — Seiji Vid Downloader Backend (with Proxy & Progress)
import os
import requests
import yt_dlp
from flask import Flask, request, jsonify, render_template, Response, stream_with_context

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/extract", methods=["POST"])
def extract():
    data = request.get_json(force=True, silent=True) or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"ok": False, "err": "URL is required."}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'skip_download': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:
                info = info['entries'][0]

            # --- BASIC INFO ---
            title = info.get('title', 'Unknown Title')
            thumbnail = info.get('thumbnail', '')
            duration = info.get('duration', 0)
            
            # --- TECH SPECS ---
            uploader = info.get('uploader', 'Unknown')
            platform = info.get('extractor_key', 'Unknown')
            views = info.get('view_count', 0)
            
            height = info.get('height', 0)
            fps = info.get('fps', 0)
            resolution = f"{height}p" if height else "HD"
            if fps and fps > 30:
                resolution += f" {fps}fps"

            filesize = info.get('filesize') or info.get('filesize_approx')
            if not filesize and 'formats' in info:
                for f in reversed(info['formats']):
                    if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                        filesize = f.get('filesize') or f.get('filesize_approx')
                        if filesize: break
            
            size_str = "Unknown Size"
            if filesize:
                size_mb = filesize / (1024 * 1024)
                if size_mb > 1024:
                    size_str = f"{size_mb/1024:.2f} GB"
                else:
                    size_str = f"{size_mb:.2f} MB"

            vcodec = info.get('vcodec', 'unknown')
            acodec = info.get('acodec', 'unknown')
            ext = info.get('ext', 'mp4')
            
            if duration:
                m, s = divmod(duration, 60)
                h, m = divmod(m, 60)
                duration_str = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            else:
                duration_str = "Unknown"

            if views >= 1_000_000:
                views_str = f"{views/1_000_000:.1f}M views"
            elif views >= 1_000:
                views_str = f"{views/1_000:.1f}K views"
            elif views > 0:
                views_str = f"{views} views"
            else:
                views_str = "No views"

            video_url = info.get('url')
            if not video_url and 'formats' in info:
                for f in reversed(info['formats']):
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        video_url = f.get('url')
                        break
            
            audio_url = None
            if 'formats' in info:
                for f in reversed(info['formats']):
                    if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                        audio_url = f.get('url')
                        break

            result = {
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration_str,
                "uploader": uploader,
                "platform": platform,
                "views": views_str,
                "resolution": resolution,
                "size": size_str,
                "vcodec": vcodec,
                "acodec": acodec,
                "ext": ext,
                "video_url": video_url,
                "audio_url": audio_url
            }

            return jsonify({"ok": True, "data": result})

    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500

@app.route("/api/download")
def download_proxy():
    target_url = request.args.get("url")
    filename = request.args.get("filename", "video.mp4")
    
    if not target_url:
        return "Missing URL", 400

    try:
        head = requests.head(target_url, allow_redirects=True)
        content_length = head.headers.get("Content-Length")

        req = requests.get(target_url, stream=True)
        
        def generate():
            for chunk in req.iter_content(chunk_size=1024*1024):
                yield chunk

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
        if content_length:
            headers["Content-Length"] = content_length

        return Response(stream_with_context(generate()), headers=headers)

    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
