"""Serve only the local original-movie preview and current build state."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
FILES = {"/": (ROOT / "web/intro/index.html", "text/html; charset=utf-8"),
         "/media/logo.mp4": (ROOT / "build/intro-preview/media/logo.mp4", "video/mp4"),
         "/media/titles.mp4": (ROOT / "build/intro-preview/media/titles.mp4", "video/mp4")}


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.respond(False)

    def do_GET(self):
        self.respond(True)

    def respond(self, body):
        route = urlsplit(self.path).path
        if route == "/api/status":
            path = ROOT / "build/web-status.json"
            state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            payload = json.dumps({"building": state.get("state") == "running",
                                  "playable": state.get("playable_verified") is True,
                                  "preview_only": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if body:
                self.wfile.write(payload)
            return
        if route not in FILES:
            self.send_error(404)
            return
        path, content_type = FILES[route]
        if not path.is_file():
            self.send_error(503, "Run prepare_intro.py first")
            return
        size = path.stat().st_size
        lo, hi, partial = 0, size - 1, False
        requested = self.headers.get("Range")
        if requested:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
            try:
                if not match or not any(match.groups()):
                    raise ValueError()
                first, last = match.groups()
                if first:
                    lo, hi = int(first), min(int(last) if last else size - 1, size - 1)
                else:
                    length = int(last)
                    if length <= 0:
                        raise ValueError()
                    lo = max(0, size - length)
                if not 0 <= lo <= hi < size:
                    raise ValueError()
                partial = True
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(hi - lo + 1))
        self.send_header("Cache-Control", "no-cache")
        if partial:
            self.send_header("Content-Range", f"bytes {lo}-{hi}/{size}")
        self.end_headers()
        if body:
            try:
                with path.open("rb") as stream:
                    stream.seek(lo)
                    remaining = hi - lo + 1
                    while remaining:
                        chunk = stream.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass  # The browser closed or sought to another video range.


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    print(f"Original intro preview: http://127.0.0.1:{args.port}/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
