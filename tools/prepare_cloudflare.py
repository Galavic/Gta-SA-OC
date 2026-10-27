"""Assemble an allowlisted Cloudflare release; never upload a local build tree."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "variants/singleplayer/build/web-site"
APP = "GTASASingleplayer"

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def prepare(output, target="workers", game_manifest=None):
    output = output.resolve()
    if not output.is_relative_to(ROOT / "build"):
        raise ValueError("Release directory must be inside the ignored build directory")
    if output.exists():
        raise ValueError("Choose a new release directory to preserve the previous release")
    assets = output / "assets"
    runtime = output / "runtime"
    assets.mkdir(parents=True)
    runtime.mkdir()
    player = SITE / "gtasa-singleplayer"
    # Compiler __FILE__ strings and package labels can embed the build machine.
    # Replace only that printable prefix, preserving Wasm section/data lengths.
    personal = re.compile(rb"C:[/\\]+Users[/\\]+[^/\\\s\"'\x00]+[/\\]+")
    def sanitized(data):
        return personal.sub(lambda m: b"/local/" + b"/" * (len(m[0]) - 7), data)
    for ext in ("wasm", "data"):
        (runtime / f"{APP}.{ext}").write_bytes(sanitized((player / f"{APP}.{ext}").read_bytes()))
    source_build_id = digest(player / f"{APP}.wasm")
    build_id = digest(runtime / f"{APP}.wasm")
    selected = ["index.html", "menu.css", "start.js", "menu-sounds.js", "contributors.js", "backgrounds.js", "music.js", "app.js", "core.js", "worker.js",
                "games.json", "gta-sa-logo.png", "background.png", "auxiliary-files.json", "hosted-import.mjs",
                "original-menu/menu.ttf", "original-menu-audio/highlight.wav", "original-menu-audio/select.wav",
                f"gtasa-singleplayer/{APP}.js"]
    if (SITE / "favicon.png").is_file():
        selected.append("favicon.png")
    if (SITE / "launcher-music.mp3").is_file():
        selected.append("launcher-music.mp3")
    selected.extend(f"social-icons/{name}.svg" for name in ("x", "github", "discord", "whatsapp"))
    selected.extend(p.name for p in sorted(SITE.glob("background-[0-9]*.png")))
    for name in selected:
        source = SITE / name
        dest = assets / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.suffix == ".js":
            dest.write_bytes(sanitized(source.read_bytes()))
        else:
            shutil.copy2(source, dest)
    # Public hosting validates a user's local DLLs; it cannot retrieve their game
    # files from the loopback server's /install route.
    shutil.copy2(ROOT / "tools/web/public-import.mjs", assets / "repair-import.mjs")
    games = json.loads((assets / "games.json").read_text(encoding="utf-8"))
    inventory = json.loads((assets / "auxiliary-files.json").read_text(encoding="utf-8"))
    game = next(g for g in games if g["id"] == inventory["id"])
    if game["sha256"] != inventory["executableSha256"]:
        raise ValueError("Auxiliary inventory belongs to another executable")
    game["requiredFiles"] = inventory["files"]
    hosted = None
    if game_manifest:
        hosted = json.loads(game_manifest.read_text(encoding="utf-8"))
        if hosted["id"] != game["id"] or hosted["executableSha256"] != game["sha256"]:
            raise ValueError("Hosted game belongs to another executable")
        files = {entry["path"]: entry for entry in hosted["entries"]}
        for file in inventory["files"]:
            if files.get(file["name"], {}).get("sha256") != file["sha256"]:
                raise ValueError("Hosted DLL does not match runtime inventory")
        shutil.copy2(game_manifest, assets / "game-assets.json")
        game["hosted"] = {"manifest": "/game-assets.json", "build": hosted["build"]}
        if hosted.get("rangeBlockSize") == 4 * 1024 * 1024:
            game["hosted"]["fastRanges"] = True
    (assets / "games.json").write_text(json.dumps(games, indent=2), encoding="utf-8")
    html = (player / "index.html").read_text(encoding="utf-8").replace(source_build_id, build_id)
    # Remove local trace transport altogether; public visitors do not POST logs.
    begin = html.index("const _beaconQ")
    end = html.index("function checkpoint", begin)
    html = html[:begin] + '''function record(text) {
  log.push(String(text));
  if (log.length > 200) log.shift();
  bootLog.textContent = log.join("\\n");
}
''' + html[end:]
    locator = r'    locateFile: (path, prefix) => /\.(wasm|data)$/.test(path) ? '
    locator += '`/runtime/' + build_id + '/${path}` : `${prefix}${path}`,'
    html, replaced = re.subn(r'    locateFile: [^\n]+', lambda match: locator, html, count=1)
    if replaced != 1:
        raise ValueError("Versioned resource locator was not found")
    translations = {
        "Importar archivos locales": "Back to launcher", "a.href = \"../seed.html\";": "a.href = \"../\";",
        "Esc: volver; mantener Esc 2 segundos: liberar el raton y salir": "Esc: back; hold Esc for 2 seconds to release the mouse and exit",
        "Salir de pantalla completa": "Exit fullscreen", "Pantalla completa": "Fullscreen",
        "Este navegador no admite mantener Esc: Esc liberara el raton y la pantalla completa.": "This browser does not support holding Esc; a short Esc releases fullscreen and the mouse.",
        "No se pudo reservar Esc; Esc corto puede liberar el raton:": "Could not capture Esc; a short Esc may release the mouse:",
        "no disponible:": "unavailable:", "No se pudo salir de pantalla completa:": "Could not exit fullscreen:",
    }
    for old, new in translations.items(): html = html.replace(old, new)
    if any(s in html for s in ("_beaconQ", "sendBeacon", 'fetch("/log"')):
        raise ValueError("Local log transport remains in public player")
    (assets / "gtasa-singleplayer/index.html").write_text(html, encoding="utf-8")
    (assets / "404.html").write_text("<!doctype html><html lang=en><meta charset=utf-8><title>Not found</title><h1>Not found</h1><a href=/>Back to launcher</a>", encoding="utf-8")
    (assets / "runtime-version.json").write_text(json.dumps({"wasmSha256": build_id, "gameplayVerified": False}), encoding="utf-8")
    shutil.copy2(ROOT / "patches/RECOMP_KIT_LICENSE", assets / "RUNTIME-LICENSE.txt")
    manifests = []
    for ext in ("wasm", "data"):
        name = f"{APP}.{ext}"
        source = player / name
        artifact = runtime / name
        manifests.append({"name": name, "key": f"{build_id}/{name}", "bytes": artifact.stat().st_size, "sha256": digest(artifact)})
    config = {
        "$schema": "https://unpkg.com/wrangler/config-schema.json",
        "name": "gta-sa-oc", "main": str(ROOT / "cloudflare/worker.mjs"),
        "compatibility_date": "2026-10-23", "workers_dev": True,
        "assets": {"directory": "./assets", "binding": "ASSETS", "run_worker_first": True, "not_found_handling": "404-page"},
        "r2_buckets": [{"binding": "GTA_RUNTIME", "bucket_name": "gta-sa-oc-runtime"}],
        "vars": {"RUNTIME_BUILD": build_id},
    }
    if hosted:
        config["vars"]["GAME_BUILD"] = hosted["build"]
    if target == "pages":
        config.pop("main")
        config.pop("assets")
        config.pop("workers_dev")
        config["name"] = "gta-galavic"
        config["pages_build_output_dir"] = "./assets"
        shutil.copy2(ROOT / "cloudflare/worker.mjs", assets / "_worker.js")
        (assets / "_routes.json").write_text(json.dumps({"version": 1, "include": ["/*"], "exclude": []}), encoding="utf-8")
    (output / "wrangler.jsonc").write_text(json.dumps(config, indent=2), encoding="utf-8")
    asset_manifest = []
    for p in sorted(assets.rglob("*")):
        if not p.is_file(): continue
        name = p.relative_to(assets).as_posix()
        if p.suffix.lower() in {".exe", ".dll", ".img", ".txd", ".dff", ".ifp", ".scm", ".wasm", ".data"}:
            raise ValueError(f"Unexpected game/runtime file in static assets: {name}")
        if p.stat().st_size > 25 * 1024 * 1024:
            raise ValueError(f"Static asset exceeds Cloudflare's file limit: {name}")
        asset_manifest.append({"path": name, "bytes": p.stat().st_size, "sha256": digest(p)})
    report = {"wasmSha256": build_id, "runtime": manifests, "assets": asset_manifest,
              "gameInstallationUploaded": bool(hosted), "selectedLauncherMediaIncluded": True, "sourceWasmSha256": source_build_id, "localLogTransport": False, "publicGameplayVerified": False,
              "gameImportRequired": not bool(hosted), "gameDllsMustMatchAuxiliaryMetadata": True,
              "hostedGameBuild": hosted["build"] if hosted else None,
              "automaticGameDownload": bool(hosted)}
    (output / "release-manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"static_files": len(asset_manifest), "runtime_bytes": sum(x['bytes'] for x in manifests), "wasm_sha256": build_id}))
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", choices=("workers", "pages"), default="workers")
    parser.add_argument("--game-manifest", type=Path, help="Prepared hosted installation inventory")
    args = parser.parse_args()
    prepare(args.output, args.target, args.game_manifest)
