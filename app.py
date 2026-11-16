import os
import requests
import yt_dlp
import json
from flask import Flask, request, jsonify, render_template, send_file, Response, stream_with_context
import subprocess
import uuid

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

# --- UNIVERSAL EXTRACTOR ---
@app.route("/api/extract", methods=["POST"])
def extract():
    data = request.get_json()
    url = data.get("url", "").strip()
    media_type = data.get("type", "video")

    if not url:
        return jsonify({"ok": False, "err": "URL is required."}), 400

    # ==========================================
    # 1. TIKTOK (TikWM Primary -> yt-dlp Fallback)
    # ==========================================
    if "tiktok.com" in url:
        try:
            # Try TikWM API
            api_url = f"https://tikwm.com/api/?url={url}"
            # Naglagay tayo ng headers para hindi agad ma-flag
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            r = requests.get(api_url, headers=headers, timeout=10)
            
            # Safe JSON parse. Kung hindi JSON, mag-e-error at dadaan sa except block
            if r.status_code == 200:
                res_json = r.json() 
                if res_json.get("code") == 0 and "data" in res_json:
                    v_data = res_json["data"]
                    direct_url = v_data.get("play") if media_type == "video" else v_data.get("music")
                    
                    if direct_url:
                        return jsonify({
                            "ok": True, 
                            "data": {
                                "title": v_data.get("title", "TikTok Media"),
                                "direct_url": direct_url
                            }
                        })
        except Exception:
            # Kung nag-fail ang TikWM (blocked or down), dedretso tayo sa yt-dlp sa baba
            pass 

    # ==========================================
    # 2. FALLBACK (yt-dlp for FB, YT, IG, and TikTok if TikWM fails)
    # ==========================================
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'nocheckcertificate': True,
        'format': 'best' if media_type == 'video' else 'bestaudio',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            direct_url = info.get('url')
            if not direct_url and 'formats' in info:
                formats = info['formats']
                direct_url = formats[-1]['url']
                
            if not direct_url:
                return jsonify({"ok": False, "err": "Could not find a valid video/audio stream."}), 404

            return jsonify({
                "ok": True, 
                "data": {
                    "title": info.get('title', 'Media Download'),
                    "direct_url": direct_url
                }
            })
    except Exception as e:
        return jsonify({"ok": False, "err": f"Extractor Error: {str(e)}"}), 500

# --- DIRECT PROXY DOWNLOADER ---
@app.route("/api/download")
def download_proxy():
    target_url = request.args.get("url")
    filename = request.args.get("filename", "seiji_download")
    
    if not target_url:
        return "No URL provided", 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.tiktok.com/"
        }
        
        req = requests.get(target_url, stream=True, headers=headers)
        
        ext = "mp4"
        if "audio" in target_url or "mime=audio" in target_url or ".mp3" in target_url:
            ext = "mp3"
            mimetype = "audio/mpeg"
        else:
            mimetype = "video/mp4"
            
        def generate():
            for chunk in req.iter_content(chunk_size=1024*1024):
                yield chunk

        return Response(stream_with_context(generate()), mimetype=mimetype, headers={
            "Content-Disposition": f'attachment; filename="{filename}.{ext}"'
        })

    except Exception as e:
        return str(e), 500

# --- LOCAL VIDEO TO MUSIC (Gallery) ---
@app.route("/api/convert-audio", methods=["POST"])
def convert_audio():
    if 'video' not in request.files:
        return jsonify({"ok": False, "err": "No video file provided"}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({"ok": False, "err": "No selected file"}), 400

    job_id = uuid.uuid4().hex[:8]
    input_path = f"/tmp/{job_id}_input.tmp"
    output_path = f"/tmp/{job_id}_audio.mp3"

    file.save(input_path)

    try:
        cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k", output_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            return jsonify({"ok": False, "err": "FFmpeg failed."}), 500

        return jsonify({
            "ok": True, 
            "data": {
                "download_url": f"/download/converted/{job_id}",
                "filename": "seiji_audio"
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

@app.route("/download/converted/<job_id>")
def dl_converted(job_id):
    output_path = f"/tmp/{job_id}_audio.mp3"
    if not os.path.exists(output_path):
        return "File not found or expired", 404
    
    return send_file(output_path, as_attachment=True, download_name="seiji_audio.mp3")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
