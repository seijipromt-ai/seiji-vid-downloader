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

# --- VIDEO TO MUSIC (FILE UPLOAD) ---
@app.route("/api/convert-audio", methods=["POST"])
def convert_audio():
    if 'video' not in request.files:
        return jsonify({"ok": False, "err": "No video file provided"}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({"ok": False, "err": "No selected file"}), 400

    # Generate unique ID for this conversion
    job_id = uuid.uuid4().hex[:8]
    input_path = f"/tmp/{job_id}_input.tmp"
    output_path = f"/tmp/{job_id}_audio.mp3"

    file.save(input_path)

    try:
        # Use ffmpeg to extract audio
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vn", "-ar", "44100", "-ac", "2", "-b:a", "320k", output_path
        ]
        
        # Run ffmpeg (suppress output to keep server clean)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            return jsonify({"ok": False, "err": "FFmpeg failed. The file might be unsupported or corrupted."}), 500

        # Instead of sending directly, we return a JSON with the download URL
        # so the frontend can show the result card first.
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
        # Cleanup input file
        if os.path.exists(input_path):
            os.remove(input_path)

@app.route("/download/converted/<job_id>")
def dl_converted(job_id):
    output_path = f"/tmp/{job_id}_audio.mp3"
    if not os.path.exists(output_path):
        return "File not found or expired", 404
    
    return send_file(output_path, as_attachment=True, download_name="seiji_audio.mp3")
    # Note: We don't delete the output path immediately because send_file needs it.
    # /tmp is automatically cleared by the OS eventually.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
