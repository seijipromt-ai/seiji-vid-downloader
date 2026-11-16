import os
import requests
from flask import Flask, request, jsonify, render_template, send_file, Response, stream_with_context
import subprocess
import uuid

app = Flask(__name__)

# Cobalt API Instance (Public)
COBALT_API = "https://api.cobalt.tools/api/json"

@app.route("/")
def index():
    return render_template("index.html")

# --- UNIVERSAL EXTRACTOR (Video & Audio) ---
@app.route("/api/extract", methods=["POST"])
def extract():
    data = request.get_json()
    url = data.get("url", "").strip()
    media_type = data.get("type", "video") # 'video' or 'audio'

    if not url:
        return jsonify({"ok": False, "err": "URL is required."}), 400

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    payload = {
        "url": url,
        "isAudioOnly": media_type == "audio",
        "vQuality": "720" # 720p is the sweet spot for mobile
    }

    try:
        r = requests.post(COBALT_API, json=payload, headers=headers, timeout=20)
        
        if r.status_code != 200:
            return jsonify({"ok": False, "err": "API busy or limit reached. Try again."}), 500

        res_data = r.json()
        
        if res_data.get("status") == "error":
            return jsonify({"ok": False, "err": res_data.get("text", "Failed to extract.")}), 400
            
        direct_url = res_data.get("url")
        
        if not direct_url:
            return jsonify({"ok": False, "err": "No media URL found."}), 400

        # Return data to frontend
        return jsonify({
            "ok": True, 
            "data": {
                "title": res_data.get("filename", "Seiji Download"),
                "direct_url": direct_url
            }
        })

    except requests.exceptions.Timeout:
        return jsonify({"ok": False, "err": "API Timeout. Please try again."}), 504
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500

# --- DIRECT PROXY DOWNLOADER ---
@app.route("/api/download")
def download_proxy():
    target_url = request.args.get("url")
    filename = request.args.get("filename", "seiji_download")
    
    if not target_url:
        return "No URL provided", 400

    try:
        req = requests.get(target_url, stream=True)
        
        # Determine extension
        ext = "mp4"
        if "audio" in target_url or ".mp3" in target_url or "mime=audio" in target_url:
            ext = "mp3"
            mimetype = "audio/mpeg"
        else:
            mimetype = "video/mp4"
            
        def generate():
            for chunk in req.iter_content(chunk_size=1024*1024):
                yield chunk

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}.{ext}"'
        }

        return Response(stream_with_context(generate()), mimetype=mimetype, headers=headers)

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
            return jsonify({"ok": False, "err": "FFmpeg failed. Unsupported format."}), 500

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
