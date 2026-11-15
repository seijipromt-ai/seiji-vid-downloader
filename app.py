import os
import yt_dlp
from flask import Flask, request, jsonify, render_template, send_file

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/tiktok", methods=["POST"])
def tiktok_info():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url: return jsonify({"ok": False, "err": "URL required"}), 400

    ydl_opts = {'quiet': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({"ok": True, "data": {
                "title": info.get('title', 'TikTok Video'),
                "thumbnail": info.get('thumbnail', ''),
                "author": info.get('uploader', 'Unknown'),
            }})
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500

@app.route("/api/audio", methods=["POST"])
def audio_info():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url: return jsonify({"ok": False, "err": "URL required"}), 400

    ydl_opts = {'quiet': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({"ok": True, "data": {
                "title": info.get('title', 'Audio Track'),
                "thumbnail": info.get('thumbnail', ''),
                "duration": info.get('duration', 0),
            }})
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500

@app.route("/download/tiktok")
def dl_tiktok():
    url = request.args.get("url")
    if not url: return "No URL", 400

    # Max quality for TikTok
    ydl_opts = {
        'outtmpl': '/tmp/tiktok_vid.%(ext)s',
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
            return send_file('/tmp/tiktok_vid.mp4', as_attachment=True, download_name="seiji_tiktok.mp4")
    except Exception as e:
        return str(e), 500

@app.route("/download/audio")
def dl_audio():
    url = request.args.get("url")
    if not url: return "No URL", 400

    # Convert to 320kbps MP3
    ydl_opts = {
        'outtmpl': '/tmp/audio_track.%(ext)s',
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'quiet': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
            return send_file('/tmp/audio_track.mp3', as_attachment=True, download_name="seiji_audio.mp3")
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
