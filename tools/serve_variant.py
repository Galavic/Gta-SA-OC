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
# Local investigation aid: the player page beacons each boot-log line here so
# a long trace (e.g. RECOMP_LOG=2) does not have to be pasted. Under build/,
# which is not tracked.
LOG = ROOT / "variants/singleplayer/build/bootlog.txt"
SEQ = ROOT / "variants/singleplayer/build/bootlog.seq"


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
    # Native test binaries can share the build output directory. Only the
    # player runtime has the preloaded resource package.
    apps = [p for p in dest.glob("*.js") if p.with_suffix(".data").is_file()]
    if len(apps) != 1:
        raise ValueError("Expected one generated runtime JavaScript file")
    template = (ROOT / "vendor/recomp-kit/web/player/index.html").read_text(encoding="utf-8")
    template = template.replace("@APP@", apps[0].stem).replace("@TITLE@", "Grand Theft Auto: San Andreas")
    template = template.replace('a.href = "../";', 'a.href = "../seed.html";')
    template = template.replace("Back to the launcher", "Importar archivos locales")
    # Ship every boot-log line to the local server (/log) so a long trace
    # never has to be pasted. A chained asynchronous writer in dispatch
    # order: batches post one at a time, so an in-flight request cannot be
    # overtaken, a failed batch is put back at the head instead of dropped,
    # and the main thread never blocks on a synchronous XHR mid-run (the
    # first transport, sync XHR every 1500 lines, throttled level-2 boots
    # visibly: ~66 blocking posts a second is a stall, not a log). Each
    # batch carries a `#B index first_line` header into bootlog.seq so a
    # later audit can still prove in-order reach; the pagehide flush is
    # the last resort when the tab closes mid-boot. A RECOMP_LOG=2 run
    # prints two lines per import call; the interval flush covers the
    # partial queue when traffic is sparse, and the bootLog repaint
    # happens on a timer so record() stays cheap.
    template = template.replace(
        "function record(text) {",
        "const _beaconQ = [];\n"
        "let _beaconBatch = 0, _beaconSent = 0, _bootDirty = false, _chain = Promise.resolve();\n"
        "function drain() {\n"
        "  if (!_beaconQ.length || !_chain) return;\n"
        "  const body = \"#B \" + (_beaconBatch++) + \" \" + _beaconSent + \"\\n\" +\n"
        "    _beaconQ.join(\"\\n\");\n"
        "  const taken = _beaconQ.splice(0, _beaconQ.length);\n"
        "  _beaconSent += taken.length;\n"
        "  _chain = _chain.then(() => fetch(\"/log\", { method: \"POST\", body }))\n"
        "    .catch(() => {\n"
        "      for (let i = taken.length - 1; i >= 0; --i) _beaconQ.unshift(taken[i]);\n"
        "      --_beaconBatch;\n"
        "      _beaconSent -= taken.length;\n"
        "    });\n"
        "}\n"
        "function beacon(text) {\n"
        "  _beaconQ.push(String(text));\n"
        "  if (_beaconQ.length >= 4096) drain();\n"
        "}\n"
        "setInterval(() => drain(), 4000);\n"
        "setInterval(() => {\n"
        "  if (!_bootDirty) return;\n"
        "  _bootDirty = false;\n"
        "  bootLog.textContent = log.join(\"\\n\");\n"
        "}, 400);\n"
        "window.addEventListener(\"pagehide\", () => {\n"
        "  if (_beaconQ.length) navigator.sendBeacon(\"/log\", \"#B \" + (_beaconBatch++) +\n"
        "    \" \" + _beaconSent + \"\\n\" + _beaconQ.join(\"\\n\"));\n"
        "});\n"
        "function record(text) {\n  beacon(text);",
        1)
    template = template.replace(
        "  log.push(String(text));\n"
        "  if (log.length > 200) log.shift();\n"
        "  bootLog.textContent = log.join(\"\\n\");",
        "  if (log.length > 200) log.shift();\n"
        "  log.push(String(text));\n"
        "  _bootDirty = true;")
    template = template.replace(
        "print: (t) => { record(t); console.log(t); },",
        "print: (t) => { record(t); },")
    template = template.replace(
        "printErr: (t) => { record(t); diagnostics.open = true; console.warn(t); },",
        "printErr: (t) => { record(t); diagnostics.open = true; },")
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

    def do_POST(self):
        """Collect a page log so a long boot trace does not have to be pasted.

        The run is a local investigation aid: the page beacons each line as it
        is recorded and the file lands under build/, which is not tracked.
        """
        path = urlsplit(self.path).path
        if path != "/log":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b""
        LOG.parent.mkdir(parents=True, exist_ok=True)
        seq_lines = []
        keep = []
        for raw in body.replace(b"\r", b"").split(b"\n"):
            if raw.startswith(b"#B "):
                seq_lines.append(raw + b" " + str(len(keep)).encode())
            else:
                keep.append(raw)
        with LOG.open("ab") as fh:
            fh.write(b"\n".join(keep) + b"\n")
        if seq_lines:
            with SEQ.open("ab") as fh:
                fh.write(b"\n".join(seq_lines) + b"\n")
        self.send_response(204)
        self.end_headers()


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
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_bytes(b"")
    SEQ.write_bytes(b"")
    print(f"Boot log: {LOG} (POST /log)", flush=True)
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.manifest = manifest
        server.import_files = {f["path"] for f in manifest["files"]}
        total = sum(f["size"] for f in manifest["files"])
        print(f"Local import: {len(manifest['files'])} files, {total} bytes", flush=True)
        print(f"http://127.0.0.1:{args.port}/seed.html", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
