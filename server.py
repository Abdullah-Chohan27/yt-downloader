import os
import re
import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE, "cookies.txt")

def cookies_args():
    return ["--cookies", COOKIES_FILE] if os.path.exists(COOKIES_FILE) else []

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
            ["yt-dlp", "--dump-json", "--no-playlist"] + cookies_args() + [url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            err = result.stderr
            if "Sign in" in err or "429" in err or "bot" in err.lower():
                return None, "YouTube blocked this server (bot detection). Upload a fresh cookies.txt to your repo — see the page for instructions."
            return None, err
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

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, path):
        with open(path, "rb") as f:
            content = f.read()
        ext = path.rsplit(".", 1)[-1].lower()
        types = {"html": "text/html", "js": "application/javascript", "css": "text/css"}
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

        if path in ("/", "/index.html"):
            self.send_static(os.path.join(BASE, "index.html"))

        elif path == "/api/info":
            url = sanitize_url(qs.get("url", [""])[0])
            if not url:
                self.send_json({"error": "Invalid or non-YouTube URL"}, 400)
                return
            info, err = get_video_info(url)
            if err or not info:
                self.send_json({"error": err or "Could not fetch video info"}, 400)
            else:
                self.send_json(info)

        elif path == "/api/stream":
            url = sanitize_url(qs.get("url", [""])[0])
            title = qs.get("title", ["video"])[0]
            if not url:
                self.send_json({"error": "Invalid URL"}, 400)
                return

            safe_title = re.sub(r'[^\w\s\-.]', '', title).strip()[:80] or "video"
            filename = safe_title + ".mp4"

            cmd = [
                "yt-dlp",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
                "--merge-output-format", "mp4",
                "--no-playlist",
            ] + cookies_args() + ["-o", "-", url]

            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                while True:
                    chunk = process.stdout.read(65536)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        process.kill()
                        break
                process.wait()
            except Exception as e:
                try:
                    self.send_json({"error": str(e)}, 500)
                except Exception:
                    pass

        elif path == "/api/cookies-status":
            self.send_json({"has_cookies": os.path.exists(COOKIES_FILE)})

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        self.send_json({"error": "Not found"}, 404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"\n✅ YTGrab running at http://localhost:{port}")
    print("🍪 cookies.txt:", "FOUND" if os.path.exists(COOKIES_FILE) else "NOT FOUND (may get bot-blocked)")
    print("   Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
