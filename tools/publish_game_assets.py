"""Publish the prepared game tree to R2 so a visitor never imports local files.

The manifest is the only description of the hosted tree: build id, per-file
size and SHA-256. The Worker streams objects under `game/<build>/<path>` and
the launcher writes them into OPFS, so the runtime keeps reading `/opfs/...`.

Usage (from the repository root):

    .venv/Scripts/python.exe tools/publish_game_assets.py manifest
    .venv/Scripts/python.exe tools/publish_game_assets.py upload --build <id>
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARED = ROOT / "variants/singleplayer/prepared"
OUTPUT = ROOT / "build/game-assets"
BUCKET = "gta-sa-oc-runtime"
WRANGLER = "wrangler@4.152.0"
# A stray duplicate of the Spanish text table that the game never loads.
EXCLUDED = {"text/spanish - copia.gxt"}
CONTENT_TYPE = "application/octet-stream"
CHUNK_SIZE = 64 * 1024 * 1024
SINGLE_OBJECT_LIMIT = 200 * 1024 * 1024


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_files(source):
    """Regular files under the prepared tree, junction folders included."""
    files = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        if relative in EXCLUDED:
            continue
        files.append({"path": relative, "size": path.stat().st_size})
    return files


def build_manifest(source=PREPARED, output=OUTPUT):
    files = source_files(source)
    for entry in files:
        entry["sha256"] = digest(source / entry["path"])
    identity = "\n".join(f"{e['path']}\0{e['sha256']}\0{e['size']}" for e in files)
    build = hashlib.sha256(identity.encode()).hexdigest()[:16]
    executable = next((e for e in files if e["path"] == "gta_sa.exe"), None)
    if executable is None:
        raise ValueError("The prepared tree has no gta_sa.exe")
    manifest = {
        "id": "gtasa-singleplayer",
        "build": build,
        "executable": "gta_sa.exe",
        "executableSha256": executable["sha256"],
        "files": len(files),
        "bytes": sum(e["size"] for e in files),
        "excluded": sorted(EXCLUDED),
        "entries": files,
    }
    target = output / build
    target.mkdir(parents=True, exist_ok=True)
    # Wrangler's single-object upload cannot carry the largest game archives.
    # Transfer chunks separately; the browser streams them into the original file.
    for entry in files:
        if entry["size"] <= SINGLE_OBJECT_LIMIT:
            continue
        entry["chunks"] = []
        with (source / entry["path"]).open("rb") as stream:
            index = 0
            while data := stream.read(CHUNK_SIZE):
                key = f"__chunks/{entry['sha256']}/{index:04d}"
                chunk = target / key
                chunk.parent.mkdir(parents=True, exist_ok=True)
                sha = hashlib.sha256(data).hexdigest()
                if not chunk.is_file() or chunk.stat().st_size != len(data) or digest(chunk) != sha:
                    chunk.write_bytes(data)
                entry["chunks"].append({"path": key, "size": len(data), "sha256": sha})
                index += 1
    previous = target / "game-assets.json"
    if previous.is_file() and not (target / "game-assets.before-chunks.json").exists():
        shutil.copy2(previous, target / "game-assets.before-chunks.json")
    (target / "game-assets.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({"build": build, "files": manifest["files"], "bytes": manifest["bytes"],
                      "manifest": str(target / "game-assets.json")}))
    return manifest, target / "game-assets.json"


def wrangler_command(key, path):
    return (f'npx {WRANGLER} r2 object put "{BUCKET}/{key}" --file "{path}" '
            f'--content-type {CONTENT_TYPE} --remote')


def upload_one(key, path, attempts=3):
    last = ""
    for attempt in range(attempts):
        result = subprocess.run(wrangler_command(key, path), shell=True,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode == 0:
            return None
        last = (result.stderr or result.stdout or "").strip()
        time.sleep(2 * (attempt + 1))
    return last[-400:]


def upload(manifest, manifest_path, source=PREPARED, jobs=6):
    state_path = manifest_path.parent / "upload-state.json"
    state = json.loads(state_path.read_text()) if state_path.is_file() else {}
    build = manifest["build"]
    objects = [chunk for e in manifest["entries"] for chunk in e.get("chunks", [e])]
    pending = [e for e in objects if state.get(e["path"]) != e["sha256"]]
    print(f"uploading {len(pending)}/{len(objects)} objects for build {build}",
          flush=True)
    done_bytes = 0
    failures = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(upload_one, f"game/{build}/{e['path']}",
                        (manifest_path.parent if e["path"].startswith("__chunks/") else source) / e["path"]): e
            for e in pending
        }
        for index, future in enumerate(as_completed(futures), 1):
            entry = futures[future]
            error = future.result()
            if error:
                failures.append({"path": entry["path"], "error": error})
                print(f"FAILED {entry['path']}: {error}", flush=True)
                continue
            state[entry["path"]] = entry["sha256"]
            done_bytes += entry["size"]
            if index % 10 == 0 or index == len(pending):
                elapsed = time.monotonic() - started
                rate = done_bytes / elapsed / (1 << 20) if elapsed else 0
                print(f"{index}/{len(pending)} objects, {done_bytes / (1 << 30):.2f} GiB, "
                      f"{rate:.1f} MiB/s", flush=True)
                state_path.write_text(json.dumps(state, indent=0), encoding="utf-8")
    state_path.write_text(json.dumps(state, indent=0), encoding="utf-8")
    if failures:
        print(json.dumps({"failed": failures}))
        return 1
    print(json.dumps({"uploaded": len(pending), "objects": len(state)}))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("manifest", "upload"))
    parser.add_argument("--source", type=Path, default=PREPARED)
    parser.add_argument("--build")
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    if args.command == "manifest":
        build_manifest(args.source, OUTPUT)
        return 0
    if not args.build:
        parser.error("upload needs --build")
    manifest_path = OUTPUT / args.build / "game-assets.json"
    manifest = json.loads(manifest_path.read_text())
    return upload(manifest, manifest_path, args.source, args.jobs)


if __name__ == "__main__":
    sys.exit(main())
