#!/usr/bin/env python3
# app.py — Seiji Vid Downloader Backend (Server-Side Merge)
import os
import requests
import yt_dlp
from flask import Flask, request, jsonify, render_template, send_file

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
        'skip_download': True,
        # Optional: Kung mag-fail ang FB, i-uncomment ang cookies.txt sa baba
        # 'cookiefile': 'cookies.txt', 
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                info = info['entries'][0]

            # --- TECH SPECS ---
            title = info.get('title', 'Unknown Title')
            thumbnail = info.get('thumbnail', '')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', 'Unknown')
            platform = info.get('extractor_key', 'Unknown')
            views = info.get('view_count', 0)
            
            height = info.get('height', 0)
            fps = info.get('fps', 0)
            resolution = f"{height}p" if height else "HD"
            if fps and fps > 30: resolution += f" {fps}fps"

            # Size logic
            filesize = info.get('filesize') or info.get('filesize_approx')
            if not filesize and 'formats' in info:
                for f in reversed(info['formats']):
                    if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                        filesize = f.get('filesize') or f.get('filesize_approx')
                        if filesize: break
            
            size_str = "Unknown Size"
            if filesize:
                size_mb = filesize / (1024 * 1024)
                size_str = f"{size_mb/1024:.2f} GB" if size_mb > 1024 else f"{size_mb:.2f} MB"

            # Has Audio/Video logic
            has_video = any(f.get('vcodec') != 'none' for f in info.get('formats', []))
            has_audio = any(f.get('acodec') != 'none' for f in info.get('formats', []))

            # Format duration
            if duration:
                m, s = divmod(duration, 60)
                h, m = divmod(m, 60)
                duration_str = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            else:
                duration_str = "Unknown"

            # Format views
            if views >= 1_000_000: views_str = f"{views/1_000_000:.1f}M views"
            elif views >= 1_000: views_str = f"{views/1_000:.1f}K views"
            elif views > 0: views_str = f"{views} views"
            else: views_str = "No views"

            result = {
                "title": title, "thumbnail": thumbnail, "duration": duration_str,
                "uploader": uploader, "platform": platform, "views": views_str,
                "resolution": resolution, "size": size_str,
                "vcodec": info.get('vcodec', 'unknown'), "ext": info.get('ext', 'mp4'),
                "has_video": has_video, "has_audio": has_audio
            }
            return jsonify({"ok": True, "data": result})

    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500

@app.route("/api/download")
def download_proxy():
    url = request.args.get("url")
    media_type = request.args.get("type", "video")
    
    if not url:
        return "Missing URL", 400

    # Ito ang magdadownload at magmemerge ng video at audio sa server
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'cookiefile': 'cookies.txt', # Kung gumawa ka ng cookies.txt, gamit ito
    }

    if media_type == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # Pilitin pagsamahin ang video at audio (bestvideo + bestaudio)
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Dito nagaganap ang download at pag-merge (download=True)
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            
            if media_type == 'audio':
                base, _ = os.path.splitext(filepath)
                filepath = base + '.mp3'

        if not os.path.exists(filepath):
            return "Download failed. File not created.", 500

        ext = filepath.split('.')[-1]
        filename = f"seiji_download.{ext}"
        mimetype = 'video/mp4' if media_type == 'video' else 'audio/mpeg'

        return send_file(filepath, as_attachment=True, download_name=filename, mimetype=mimetype)
        
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
