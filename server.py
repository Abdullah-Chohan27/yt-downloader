import os
import re
import json
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

progress_data = {}

def sanitize_url(url):
    url = url.strip()
    if not re.match(r'^https?://', url):
        return None
    if not re.search(r'(youtube\.com|youtu\.be)', url):
        return None
    return url

def get_video_info(url):
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return None, result.stderr
        info = json.loads(result.stdout)
        return {
            "title": info.get("title", "Unknown"),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration_string", "N/A"),
            "uploader": info.get("uploader", "Unknown"),
            "view_count": info.get("view_count", 0),
        }, None
    except Exception as e:
        return None, str(e)

def download_video(url, job_id):
    progress_data[job_id] = {"status": "downloading", "percent": 0, "filename": "", "error": ""}

    output_template = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    def progress_hook(line):
        # Parse yt-dlp progress output
        match = re.search(r'(\d+\.?\d*)%', line)
        if match:
            progress_data[job_id]["percent"] = float(match.group(1))
        dest_match = re.search(r'Destination: (.+)', line)
        if dest_match:
            progress_data[job_id]["filename"] = os.path.basename(dest_match.group(1).strip())
        merge_match = re.search(r'Merging formats into "(.+)"', line)
        if merge_match:
            progress_data[job_id]["filename"] = os.path.basename(merge_match.group(1).strip())

    try:
        cmd = [
            "yt-dlp",
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            "--no-playlist",
            "--newline",
            url
        ]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in process.stdout:
            progress_hook(line)
        process.wait()

        if process.returncode == 0:
            progress_data[job_id]["status"] = "done"
            progress_data[job_id]["percent"] = 100
        else:
            progress_data[job_id]["status"] = "error"
            progress_data[job_id]["error"] = "Download failed. Check the URL and try again."
    except Exception as e:
        progress_data[job_id]["status"] = "error"
        progress_data[job_id]["error"] = str(e)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logging

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        with open(path, "rb") as f:
            content = f.read()
        ext = path.rsplit(".", 1)[-1].lower()
        types = {"html": "text/html", "js": "application/javascript", "css": "text/css", "ico": "image/x-icon"}
        ctype = types.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.send_file(os.path.join(os.path.dirname(__file__), "index.html"))
        elif path == "/api/info":
            url = qs.get("url", [""])[0]
            url = sanitize_url(url)
            if not url:
                self.send_json({"error": "Invalid or non-YouTube URL"}, 400)
                return
            info, err = get_video_info(url)
            if err or not info:
                self.send_json({"error": err or "Could not fetch video info"}, 400)
            else:
                self.send_json(info)
        elif path == "/api/progress":
            job_id = qs.get("job_id", [""])[0]
            data = progress_data.get(job_id, {"status": "not_found"})
            self.send_json(data)
        elif path == "/api/downloads":
            files = []
            for f in os.listdir(DOWNLOAD_DIR):
                fp = os.path.join(DOWNLOAD_DIR, f)
                if os.path.isfile(fp):
                    files.append({"name": f, "size": os.path.getsize(fp)})
            files.sort(key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x["name"])), reverse=True)
            self.send_json(files)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/download":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            url = sanitize_url(body.get("url", ""))
            if not url:
                self.send_json({"error": "Invalid or non-YouTube URL"}, 400)
                return
            job_id = str(hash(url + str(threading.get_ident())))[-8:]
            thread = threading.Thread(target=download_video, args=(url, job_id), daemon=True)
            thread.start()
            self.send_json({"job_id": job_id})
        else:
            self.send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"\n✅ YouTube Downloader running at http://localhost:{port}")
    print(f"📁 Downloads will be saved to: {DOWNLOAD_DIR}")
    print("   Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
