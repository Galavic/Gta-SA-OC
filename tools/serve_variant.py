"""Serve the prepared singleplayer build and import its local files into OPFS.

Only prepared inputs are exposed, on loopback. Browser files and profiles are
separate; importing never touches saves or modifies the installed game.
"""
import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "variants/singleplayer/build/web-site"
PREPARED = ROOT / "variants/singleplayer/prepared"
GAME_ID = "gtasa-singleplayer"


def import_manifest(prepared=PREPARED, site=SITE):
    """Inventory staged inputs, including files behind prepared folder links."""
    game = next(g for g in json.loads((site / "games.json").read_text()) if g["id"] == GAME_ID)
    files = []
    for top in sorted(prepared.iterdir()):
        candidates = sorted(top.rglob("*")) if top.is_dir() else [top]
        for path in candidates:
            if path.is_file():
                info = path.stat()
                files.append({"path": path.relative_to(prepared).as_posix(),
                              "size": info.st_size, "mtime": int(info.st_mtime), "isDir": False})
    names = {f["path"] for f in files}
    if game["executable"] not in names:
        raise ValueError("Prepared executable is missing")
    for folder in game["requiredDirs"]:
        if not any(n.startswith(folder + "/") for n in names):
            raise ValueError(f"Prepared asset folder is empty or missing: {folder}")
    return {"game": game, "files": files}


def stage_player(site=SITE):
    """Refresh only HTML; preserve the generated Wasm executable."""
    dest = site / GAME_ID
    apps = list(dest.glob("*.js"))
    if len(apps) != 1:
        raise ValueError("Expected one generated runtime JavaScript file")
    template = (ROOT / "vendor/recomp-kit/web/player/index.html").read_text(encoding="utf-8")
    template = template.replace("@APP@", apps[0].stem).replace("@TITLE@", "Grand Theft Auto: San Andreas")
    template = template.replace('a.href = "../";', 'a.href = "../seed.html";')
    template = template.replace("Back to the launcher", "Importar archivos locales")
    (dest / "index.html").write_text(template, encoding="utf-8")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass

    def send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/seed-manifest":
            self.send_bytes(json.dumps(self.server.manifest).encode(), "application/json")
            return
        if path == "/seed.html":
            self.send_bytes((ROOT / "tools/web/local-seed.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path.startswith("/install/"):
            rel = unquote(path[len("/install/"):])
            # Exact inventory allowlist excludes traversal and installed loaders.
            if rel not in self.server.import_files:
                self.send_error(404)
                return
            candidate = PREPARED / rel
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(candidate.stat().st_size))
            self.end_headers()
            try:
                with candidate.open("rb") as fh:
                    while chunk := fh.read(1 << 20):
                        self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        return super().do_GET()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--only", default="",
                        help="Comma-separated path prefixes to expose (subset import for iteration)")
    args = parser.parse_args()
    manifest = import_manifest()
    if args.only:
        prefixes = [p for p in args.only.split(",") if p]
        before = len(manifest["files"])
        manifest["files"] = [f for f in manifest["files"]
                             if f["path"] == "gta_sa.exe"
                             or any(f["path"].startswith(p) for p in prefixes)]
        print(f"Subset: {len(manifest['files'])}/{before} files", flush=True)
    stage_player()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.manifest = manifest
        server.import_files = {f["path"] for f in manifest["files"]}
        total = sum(f["size"] for f in manifest["files"])
        print(f"Local import: {len(manifest['files'])} files, {total} bytes", flush=True)
        print(f"http://127.0.0.1:{args.port}/seed.html", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
