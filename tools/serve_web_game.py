"""Serve the real web launcher locally while the build publishes its artifacts."""
import argparse
from pathlib import Path
import sys
import functools
import hashlib
import http.server
import json
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools"))
import web_launcher


class InstalledGameHandler(web_launcher.IsolatedHandler):
    """Expose only the verified installation to the local OPFS importer."""

    def send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        """Keep runtime diagnostics locally so the next boot fault can be inspected."""
        if urlsplit(self.path).path != "/local-runtime-log":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 65536:
            self.send_error(413)
            return
        try:
            lines = json.loads(self.rfile.read(length))
            if not isinstance(lines, list) or len(lines) > 100:
                raise ValueError("Invalid log batch")
            with (ROOT / "build/browser-runtime.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps(lines, ensure_ascii=False) + "\n")
        except (ValueError, UnicodeError):
            self.send_error(400)
            return
        self.send_bytes(b"{}", "application/json")

    def do_GET(self):
        route = urlsplit(self.path).path
        if route in ("/gtasa/", "/gtasa/index.html"):
            page = (ROOT / "build/web-site/gtasa/index.html").read_text(encoding="utf-8")
            page = page.replace('const log = [];', '''const log = [];
const diagnostics = [];
let diagnosticLogCursor = 0;
let lastDownloadDiagnostic = 0;
function recordDiagnostic(text) {
  if (String(text).startsWith("STATUS: Downloading")) {
    const now = Date.now();
    if (now - lastDownloadDiagnostic < 1000) return;
    lastDownloadDiagnostic = now;
  }
  if (diagnostics.length < 1000) diagnostics.push(String(text).slice(0, 4000));
}
function flushFailureDiagnostic(text) {
  recordDiagnostic(text + "\\n" + new Error("Runtime failure stack").stack);
  // Retain all missing-code reports, rather than the last twelve, so the
  // next correction can handle the whole startup batch in one pass.
  const messages = [...new Set([...log.slice(diagnosticLogCursor), ...diagnostics.splice(0)])]
    .filter(t => !t.startsWith("STATUS: Downloading"));
  diagnosticLogCursor = log.length;
  let batch = [];
  function send() {
    if (!batch.length) return;
    fetch("/local-runtime-log", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(batch) }).catch(() => {});
    batch = [];
  }
  for (const message of messages) {
    const bounded = String(message).slice(0, 4000);
    if (batch.length >= 40 || new TextEncoder().encode(JSON.stringify([...batch, bounded])).length > 60000) send();
    batch.push(bounded);
  }
  send();
}
function runtimeFailure(what) {
  const reason = [...log].reverse().find(t => /no block entry|fatal:|not supported|unimplemented import|no shim registered|refusing to skip|strict imports:|unallocated trampoline/i.test(t));
  flushFailureDiagnostic("ABORT: " + what);
  status("El juego se detuvo durante el arranque.\\n" + (reason || what), true);
}
setInterval(() => {
  if (!diagnostics.length) return;
  const batch = diagnostics.splice(0, 10);
  fetch("/local-runtime-log", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(batch) }).catch(() => {});
}, 1000);
window.addEventListener("error", e => flushFailureDiagnostic("ERROR: " + e.message + "\\n" + (e.error?.stack || "")));
window.addEventListener("unhandledrejection", e => flushFailureDiagnostic("REJECTION: " + e.reason + "\\n" + (e.reason?.stack || "")));
recordDiagnostic("Player loaded " + new Date().toISOString());''')
            page = page.replace('statusEl.textContent = text;', 'statusEl.textContent = text; recordDiagnostic("STATUS: " + text);')
            page = page.replace('log.push(t);', 'log.push(t); recordDiagnostic(t);')
            page = page.replace('m.ENV.RECOMP_PROFILE_DIR = `/opfs/${id}/profile`;',
                                'm.ENV.RECOMP_PROFILE_DIR = `/opfs/${id}/profile`; m.ENV.RECOMP_STRICT_UNKNOWN = "1"; m.ENV.RECOMP_STRICT_IMPORTS = "1";')
            page = page.replace('onAbort: (what) => status(`The game stopped: ${what}`, true),',
                                'onAbort: (what) => runtimeFailure(what),')
            self.send_bytes(page.encode("utf-8"), "text/html; charset=utf-8")
            return
        if route == "/local-install.json":
            self.send_bytes(json.dumps(self.server.install_manifest).encode(), "application/json")
            return
        if route.startswith("/local-game/"):
            name = unquote(route[len("/local-game/"):])
            source = self.server.install_files.get(name)
            if source is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(source.stat().st_size))
            self.end_headers()
            try:
                with source.open("rb") as stream:
                    self.copyfile(stream, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass  # User cancelled the import.
            return
        if route in ("/app.js", "/worker.js"):
            source = (ROOT / "build/web-site" / route[1:]).read_text(encoding="utf-8")
            if route == "/worker.js":
                source = source.replace('if (kind === "files") source = filesSource(files);', '''if (kind === "local") {
      const response = await fetch("/local-install.json", { signal: controller.signal });
      if (!response.ok) throw new Error("No se pudo leer la instalación local");
      const install = await response.json();
      if (install.available === false) throw new Error(install.error);
      source = {
        list: async () => install.entries,
        stream: async (entry) => {
          const response = await fetch("/local-game/" + entry.path.split("/").map(encodeURIComponent).join("/"), { signal: controller.signal });
          if (!response.ok) throw new Error("No se pudo leer " + entry.path);
          return response.body;
        },
      };
    }
    else if (kind === "files") source = filesSource(files);''')
            else:
                source += '''
// The loopback server has verified this user's installation, including its EXE.
const localCard = cards.get("gtasa");
if (localCard) {
  try {
    const response = await fetch("/local-install.json");
    if (!response.ok) throw new Error("Instalación local no disponible");
    const install = await response.json();
    if (install.available === false) throw new Error(install.error);
    const button = document.createElement("button");
    button.className = "import-folder";
    button.textContent = "Importar mi GTA instalado";
    button.onclick = () => runImport(localCard, { kind: "local" });
    localCard.el.querySelector(".import-folder").before(button);
    if (localCard.state !== "ready") {
      show(localCard, "Carpeta detectada: " + install.folder);
      await runImport(localCard, { kind: "local" });
    }
  } catch (error) {
    show(localCard, error.message, true);
  }
}
'''
            self.send_bytes(source.encode("utf-8"), "text/javascript; charset=utf-8")
            return
        super().do_GET()


def installed_files():
    """Follow prepared asset junctions, retaining the prepared auxiliary DLLs."""
    folder = ROOT / "prepared"
    selection = ROOT / "variants/singleplayer/preparation.json"
    if selection.is_file():
        profile = json.loads(selection.read_text(encoding="utf-8"))
        folder = Path(profile["staged_image"]).parent
    game = json.loads((ROOT / "build/web-site/games.json").read_text())[0]
    exe = folder / game["executable"]
    if hashlib.sha256(exe.read_bytes()).hexdigest() != game["sha256"]:
        raise ValueError("La carpeta de GTA ya está reconocida. Su ejecutable está en análisis; "
                         "el Wasm anterior corresponde a otra versión.")
    for name in game["requiredDirs"]:
        if not (folder / name).is_dir():
            raise ValueError("Missing installation directory: " + name)
    files = {}
    entries = []
    def walk(directory, prefix=""):
        for item in sorted(directory.iterdir()):
            relative = prefix + item.name
            stat = item.stat()
            is_dir = item.is_dir()
            entries.append(dict(path=relative, size=0 if is_dir else stat.st_size,
                                mtime=int(stat.st_mtime), isDir=is_dir))
            if is_dir:
                walk(item, relative + "/")
            elif item.is_file():
                files[relative] = item
    walk(folder)
    return files, dict(folder=str(folder), entries=entries, available=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    site = ROOT / "build/web-site"
    if not (site / "games.json").is_file():
        web_launcher.build([ROOT], site)
    # The build supervisor publishes the real .js/.wasm/.data files here
    # after successful linking. This server neither creates substitutes nor
    # treats the launcher page as evidence of game execution.
    try:
        files, manifest = installed_files()
    except (OSError, ValueError) as error:
        # A moved installation must not prevent serving the player or the
        # existing browser import. Never present an empty tree as a valid GTA.
        files = {}
        selected = ROOT / "variants/singleplayer/preparation.json"
        profile = json.loads(selected.read_text(encoding="utf-8")) if selected.is_file() else {}
        manifest = dict(folder=str(ROOT / "prepared"), entries=[], available=False,
                        installation=profile.get("installation"),
                        assets_available=bool(profile and all((Path(profile["installation"]) / name).is_dir()
                                              for name in profile["included_asset_directories"])),
                        error=str(error) if profile else
                        "La carpeta local de GTA no está disponible. Selecciona su ubicación actual con Importar carpeta.")
        print("Local installation unavailable: " + str(error), flush=True)
    handler = functools.partial(InstalledGameHandler, directory=str(site))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        server.install_files = files
        server.install_manifest = manifest
        print("Serving player at http://127.0.0.1:%d/; local assets available=%s" %
              (args.port, manifest["available"]), flush=True)
        server.serve_forever()
