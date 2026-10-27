"""Serve the prepared singleplayer build and import its local files into OPFS.

Only prepared inputs are exposed, on loopback. Browser files and profiles are
separate; importing never touches saves or modifies the installed game.
"""
import argparse
import json
import shutil
import subprocess
import hashlib
import tomllib
import sys
import os
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


def stage_launcher(site=SITE, prepared=PREPARED, assets=ROOT / "build/launcher-assets"):
    """Restore the local launcher design after a runtime web build replaces it."""
    site.mkdir(parents=True, exist_ok=True)
    for name in ("app.js", "core.js", "worker.js"):
        shutil.copy2(ROOT / "vendor/recomp-kit/web/launcher" / name, site / name)
    shutil.copy2(ROOT / "tools/web/hosted-import.mjs", site / "hosted-import.mjs")
    worker = site / "worker.js"
    worker.write_text(worker.read_text(encoding="utf-8").replace(
        "    controller = new AbortController();",
        '    controller = new AbortController();\n'
        '    if (kind === "hosted" && game.hosted.fastRanges) {\n'
        '      const { importHostedGame } = await import("./hosted-import.mjs");\n'
        '      try {\n'
        '        return await importHostedGame(game, await dirFor(game.id + "/game"), {\n'
        '          signal: controller.signal, freeBytes: await freeBytes(),\n'
        '          onProgress: p => postMessage({ progress: p }),\n'
        '        });\n'
        '      } finally { controller = null; }\n'
        '    }', 1), encoding="utf-8")
    for name in ("index.html", "start.js", "menu.css", "menu-sounds.js", "contributors.js", "backgrounds.js", "music.js"):
        shutil.copy2(ROOT / "tools/web/launcher" / name, site / name)
    shutil.copytree(ROOT / "tools/web/launcher/social-icons", site / "social-icons", dirs_exist_ok=True)
    app = site / "app.js"
    app.write_text(app.read_text(encoding="utf-8").replace(
        "if (found) location.href = url.href;",
        "if (found) { await window.recompMenuAudio?.waitForSelection?.(); location.href = url.href; }").replace(
        '${humanBytes(p.bytesTotal)} — ${p.current}`;',
        '${humanBytes(p.bytesTotal)} — ${p.current}${p.bytesPerSecond ? ` — ${humanBytes(p.bytesPerSecond)}/s` : ""}`;'),
        encoding="utf-8")
    shutil.copy2(ROOT / "web/recreation/public/js/font-layout.mjs", site / "font-layout.mjs")
    logo = assets / "gta-sa-logo.png"
    if logo.is_file():
        shutil.copy2(logo, site / "gta-sa-logo.png")
    background = assets / "background.png"
    if background.is_file():
        shutil.copy2(background, site / "background.png")
    for cover in sorted(assets.glob("background-[0-9]*.png")):
        shutil.copy2(cover, site / cover.name)
    favicon = assets / "favicon.png"
    if favicon.is_file():
        shutil.copy2(favicon, site / "favicon.png")
    music = assets / "launcher-music.mp3"
    if music.is_file():
        shutil.copy2(music, site / "launcher-music.mp3")
    # Decode the installed font locally; never include its rasters/metrics in Git.
    font_source = prepared / "models/fonts.txd"
    metrics_source = prepared / "data/fonts.dat"
    output = site / "original-menu"
    exporter = ROOT / "tools/web/launcher/export-font.mjs"
    font_builder = ROOT / "tools/web/launcher/build-menu-font.py"
    if font_source.is_file() and metrics_source.is_file():
        stamp = output / "metrics.json"
        if (not stamp.is_file() or stamp.stat().st_mtime <
                max(font_source.stat().st_mtime, metrics_source.stat().st_mtime, exporter.stat().st_mtime)):
            node = shutil.which("node")
            if node:
                subprocess.run([node, str(exporter), str(prepared), str(output)], check=True)
        font = output / "menu.ttf"
        if stamp.is_file() and (not font.is_file() or font.stat().st_mtime <
                                max(stamp.stat().st_mtime, font_builder.stat().st_mtime)):
            subprocess.run([sys.executable, str(font_builder), str(output)], check=True)
    # Optional local background images remain in the site.
    audio_sources = [prepared / "audio" / name for name in
                     ("CONFIG/BankLkup.dat", "CONFIG/PakFiles.dat", "SFX/GENRL")]
    if all(path.is_file() for path in audio_sources):
        audio_exporter = ROOT / "web/recreation/tools/export-menu-audio.mjs"
        audio_output = site / "original-menu-audio"
        audio_stamp = audio_output / "manifest.json"
        if (not audio_stamp.is_file() or not all((audio_output / name).is_file()
                for name in ("highlight.wav", "select.wav")) or audio_stamp.stat().st_mtime <
                max(audio_exporter.stat().st_mtime, *(path.stat().st_mtime for path in audio_sources))):
            node = shutil.which("node")
            if node:
                subprocess.run([node, str(audio_exporter), str(audio_output), "--menu-only"],
                               env={**os.environ, "SA_PATH": str(prepared)}, check=True)


def stage_auxiliary_files(site=SITE, game_dir=ROOT / "variants/singleplayer"):
    """Bind the local repair inventory to the configured executable and DLL hashes."""
    cfg = tomllib.loads((game_dir / "game.toml").read_text(encoding="utf-8"))
    files = []
    for module in cfg.get("modules", {}).get("aux", {}).values():
        path = game_dir / module["path"]
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        if sha != module["sha256"]:
            raise ValueError(f"Auxiliary file does not match configured image: {module['name']}")
        files.append({"name": module["name"], "sha256": sha, "size": path.stat().st_size})
    inventory = {"id": cfg["game"]["id"], "executableSha256": cfg["game"]["sha256"], "files": files}
    (site / "auxiliary-files.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "tools/web/repair-import.mjs", site / "repair-import.mjs")


def stage_player(site=SITE, game_dir=ROOT / "variants/singleplayer"):
    """Refresh only HTML; preserve the generated Wasm executable."""
    dest = site / GAME_ID
    # Native test binaries can share the build output directory. Only the
    # player runtime has the preloaded resource package.
    apps = [p for p in dest.glob("*.js") if p.with_suffix(".data").is_file()]
    if len(apps) != 1:
        raise ValueError("Expected one generated runtime JavaScript file")
    template = (ROOT / "vendor/recomp-kit/web/player/index.html").read_text(encoding="utf-8")
    template = template.replace("@APP@", apps[0].stem).replace("@TITLE@", "Grand Theft Auto: San Andreas")
    # The high-performance preference is already requested by the player.
    # Record the selected adapter once so integrated/discrete selection can
    # be checked from the local boot log without adding per-frame work.
    template = template.replace(
        '  const wanted = [',
        '  try {\n'
        '    const info = adapter.info || {};\n'
        '    record("WebGPU adapter: " + JSON.stringify({ vendor: info.vendor || "",\n'
        '      architecture: info.architecture || "", device: info.device || "",\n'
        '      description: info.description || "" }));\n'
        '  } catch { record("WebGPU adapter information unavailable"); }\n'
        '  const wanted = [', 1)
    wasm = apps[0].with_suffix(".wasm")
    with wasm.open("rb") as stream:
        build_id = hashlib.file_digest(stream, "sha256").hexdigest()
    template = template.replace(
        '  checkpoint("WebGPU device ready; loading WebAssembly");',
        '  checkpoint("Player build: ' + build_id + '");\n'
        '  checkpoint("WebGPU device ready; loading WebAssembly");', 1)
    template = template.replace(
        '    canvas,',
        '    canvas,\n    locateFile: (path, prefix) => `${prefix}${path}?build=' + build_id[:16] + '`,', 1)
    template = template.replace(
        'script.src = "@APP@.js";'.replace("@APP@", apps[0].stem),
        'script.src = "' + apps[0].stem + '.js?build=' + build_id[:16] + '";', 1)

    template = template.replace('a.href = "../";', 'a.href = "../seed.html";')
    template = template.replace("Back to the launcher", "Importar archivos locales")
    stage_auxiliary_files(site, game_dir)
    template = template.replace(
        '  checkpoint("Game files imported; requesting WebGPU device");',
        '  const { repairAuxiliaryFiles } = await import("../repair-import.mjs");\n'
        '  await repairAuxiliaryFiles(dir, game, { report: checkpoint });\n'
        '  checkpoint("Game files imported; requesting WebGPU device");', 1)
    # Bare player URLs must not silently skip a missing routine and corrupt
    # its caller's stack. Explicit RECOMP_ query options still override this.
    template = template.replace(
        "m.ENV.RECOMP_PROFILE_DIR =",
        'm.ENV.RECOMP_STRICT_UNKNOWN = "1";\n'
        '      m.ENV.RECOMP_READ_PATH_CACHE = "1";\n'
        '      delete m.ENV.RECOMP_D3D9_SCALE;\n'
        '      m.ENV.RECOMP_D3D9_FRAME_GROUP_CACHE = "1";\n'
        '      m.ENV.RECOMP_D3D9_BATCH_UPLOADS = "1";\n'
        '      m.ENV.RECOMP_D3D9_RENAME_BUFFERS = "1";\n'
        '      m.ENV.RECOMP_D3D9_STATS = "1";\n'
        '      m.ENV.RECOMP_PROFILE_DIR =',
        1)
    # Retire the QPC experiment from the playable launcher. Old shared links
    # must not accelerate physics/animation, even when they still request 2x.
    template = template.replace(
        'for (const [k, v] of extra) if (k.startsWith("RECOMP_")) m.ENV[k] = v;',
        'for (const [k, v] of extra) if (k.startsWith("RECOMP_") && k !== "RECOMP_QPC_SCALE") m.ENV[k] = v;\n'
        '      m.ENV.RECOMP_QPC_SCALE = "1";\n'
        '      record("Runtime config: " + JSON.stringify({ qpcScale: m.ENV.RECOMP_QPC_SCALE, '
        'renderScale: m.ENV.RECOMP_D3D9_SCALE || "auto", readPathCache: m.ENV.RECOMP_READ_PATH_CACHE, '
        'frameGroupCache: m.ENV.RECOMP_D3D9_FRAME_GROUP_CACHE, '
        'batchUploads: m.ENV.RECOMP_D3D9_BATCH_UPLOADS, '
        'bufferRenaming: m.ENV.RECOMP_D3D9_RENAME_BUFFERS }));', 1)
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
    template = template.replace('<details id="diagnostics">', '<details id="diagnostics" hidden>', 1)
    # Hide the whole overlay, including its summary. Logging and local trace
    # collection continue, and subsequent warnings cannot undo the user's choice.
    template = template.replace(
        "</style>",
        '#diagnostics { bottom: 48px; }\n'
        '#diagnostics[hidden] { display: none; }\n'
        '#toggle-logs { position: fixed; bottom: 8px; right: 8px; z-index: 2; '
        'padding: 6px 10px; background: #151515e8; color: #ddd; '
        'border: 1px solid #666; border-radius: 4px; cursor: pointer; }\n'
        '</style>', 1)
    template = template.replace(
        '<script>',
        '<button id="toggle-logs" type="button" aria-controls="diagnostics" '
        'aria-expanded="false" title="Show or hide logs (F8)">Show logs · F8</button>\n<script>', 1)
    template = template.replace(
        'start().catch((e) => fail(e.message));',
        'const logToggle = document.getElementById("toggle-logs");\n'
        'function toggleLogs() {\n'
        '  diagnostics.hidden = !diagnostics.hidden;\n'
        '  if (!diagnostics.hidden) diagnostics.open = true;\n'
        '  logToggle.textContent = diagnostics.hidden ? "Show logs · F8" : "Hide logs · F8";\n'
        '  logToggle.setAttribute("aria-expanded", String(!diagnostics.hidden));\n'
        '  canvas.focus();\n'
        '}\n'
        'logToggle.addEventListener("click", toggleLogs);\n'
        'window.addEventListener("keydown", (event) => {\n'
        '  if (event.code !== "F8" || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;\n'
        '  event.preventDefault();\n'
        '  event.stopImmediatePropagation();\n'
        '  if (!event.repeat) toggleLogs();\n'
        '}, true);\n'
        'window.addEventListener("keyup", (event) => {\n'
        '  if (event.code !== "F8") return;\n'
        '  event.preventDefault();\n'
        '  event.stopImmediatePropagation();\n'
        '}, true);\n'
        'start().catch((e) => fail(e.message));', 1)
    (dest / "index.html").write_text(template, encoding="utf-8")


class Handler(SimpleHTTPRequestHandler):
    # Windows registry MIME associations can classify .mjs as text/plain.
    # Browsers enforce JavaScript MIME types for every ES module import.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".mjs": "application/javascript",
        ".js": "application/javascript",
        ".wasm": "application/wasm",
        ".ttf": "font/ttf",
    }

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
    stage_launcher()
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
