import os
import yt_dlp
import subprocess
import uuid
from flask import Flask, request, jsonify, render_template, send_file

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

# --- TIKTOK DOWNLOADER ---
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

@app.route("/download/tiktok")
def dl_tiktok():
    url = request.args.get("url")
    if not url: return "No URL", 400

    job_id = uuid.uuid4().hex[:8]
    temp_in = f"/tmp/{job_id}_raw.%(ext)s"
    final_out = f"/tmp/{job_id}_final.mp4"

    # 1. Limit to 720p max to prevent playback errors on mid-range phones
    ydl_opts = {
        'outtmpl': temp_in,
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'quiet': True,
        'merge_output_format': 'mp4'
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            raw_file = ydl.prepare_filename(info)
            if not os.path.exists(raw_file):
                raw_file = raw_file.replace('.webm', '.mp4').replace('.mkv', '.mp4')

        # 2. Re-encode with lower bitrate (CRF 28) and scale to exactly 720p
        # -vf "scale=-2:720" ensures it fits vertically even if it's a horizontal video
        cmd = [
            "ffmpeg", "-y", "-i", raw_file,
            "-vf", "scale=-2:720", 
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", 
            "-c:a", "aac", "-b:a", "128k", 
            "-movflags", "+faststart", 
            final_out
        ]
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if os.path.exists(raw_file): os.remove(raw_file)
        
        return send_file(final_out, as_attachment=True, download_name="seiji_tiktok.mp4")
        
    except Exception as e:
        return str(e), 500

# --- VIDEO TO MUSIC (FILE UPLOAD) ---
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
        # Standard 192kbps MP3 (high quality pero maliit ang size)
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k", output_path
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            return jsonify({"ok": False, "err": "FFmpeg failed. Unsupported format."}), 500

        return jsonify({
            "ok": True, 
            "data": {
                "download_url": f"/download/converted/{job_id}",
                "filename": file.filename
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
