"""Check a published allowlisted release, including gzip round trips and ranges.

These are transport checks. Browser gameplay is separate evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
import zlib


def verify(release, base_url):
    manifest = json.loads((release / "release-manifest.json").read_text(encoding="utf-8"))
    assets = release / "assets"
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(), "base_url": base_url,
              "runtime_build": manifest["wasmSha256"], "assets": [], "runtime": [],
              "browser_gameplay_verified": False}

    def request(path, encoding="identity", method="GET", headers=None):
        return urlopen(Request(base_url.rstrip("/") + "/" + path.lstrip("/"), method=method,
                               headers={"Accept-Encoding": encoding, **(headers or {})}), timeout=90)

    def isolation(response):
        assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
        assert response.headers.get("Cross-Origin-Embedder-Policy") == "require-corp"

    for item in manifest["assets"]:
        if item["path"].startswith("_"):
            continue
        with request(item["path"]) as response:
            isolation(response)
            data = response.read()
            assert len(data) == item["bytes"], item["path"]
            assert hashlib.sha256(data).hexdigest() == item["sha256"], item["path"]
            if item["path"].endswith((".js", ".mjs")):
                assert response.headers.get_content_type() in {"application/javascript", "text/javascript"}, item["path"]
            report["assets"].append({"path": item["path"], "bytes": len(data), "sha256_verified": True})

    runtime = {item["name"]: item for item in manifest["runtime"]}
    for name, item in runtime.items():
        if name.endswith(".gz"):
            continue
        path = f"runtime/{manifest['wasmSha256']}/{name}"
        with request(path, method="HEAD") as response:
            isolation(response)
            assert int(response.headers["Content-Length"]) == item["bytes"], name
            assert response.headers.get("Content-Encoding") is None, name
        encoded = runtime.get(name + ".gz")
        if not encoded:
            continue
        compressed, decoded = hashlib.sha256(), hashlib.sha256()
        size = decoded_size = 0
        inflater = zlib.decompressobj(zlib.MAX_WBITS | 16)
        with request(path, encoding="gzip") as response:
            isolation(response)
            assert response.headers.get("Content-Encoding") == "gzip", name
            assert response.headers.get("Vary") and "accept-encoding" in response.headers["Vary"].lower()
            expected_type = "application/wasm" if name.endswith(".wasm") else "application/octet-stream"
            assert response.headers.get_content_type() == expected_type, name
            while chunk := response.read(1 << 20):
                compressed.update(chunk)
                size += len(chunk)
                original = inflater.decompress(chunk)
                decoded.update(original)
                decoded_size += len(original)
            tail = inflater.flush()
            decoded.update(tail)
            decoded_size += len(tail)
        assert inflater.eof and not inflater.unused_data, name
        assert size == encoded["bytes"] and compressed.hexdigest() == encoded["sha256"], name
        assert decoded_size == item["bytes"] and decoded.hexdigest() == item["sha256"], name
        report["runtime"].append({"name": name, "gzip_bytes": size, "decoded_bytes": decoded_size,
                                  "gzip_sha256_verified": True, "decoded_sha256_verified": True})

    games = json.loads((assets / "games.json").read_text(encoding="utf-8"))
    if manifest.get("demandFiles"):
        game = next(game for game in games if game.get("hosted", {}).get("demandFiles"))
        inventory = json.loads((assets / "game-assets.json").read_text(encoding="utf-8"))
        entry = max(inventory["entries"], key=lambda entry: entry["size"])
        obj = entry.get("chunks", [entry])[0]
        size = min(inventory["rangeBlockSize"], obj["size"])
        path = f"game/{game['hosted']['build']}/{obj['path']}"
        with request(path, headers={"Range": f"bytes=0-{size - 1}"}) as response:
            isolation(response)
            assert response.status == 206
            assert response.headers["Content-Range"] == f"bytes 0-{size - 1}/{obj['size']}"
            assert response.headers.get("Content-Encoding") is None
            data = response.read()
            assert len(data) == size and hashlib.sha256(data).hexdigest() == obj["ranges"][0]
        report["game_range"] = {"object": obj["path"], "bytes": size, "sha256_verified": True}
    report["passed"] = True
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--base-url", default="https://gta.galavic.world")
    parser.add_argument("--output", type=Path, default=Path("build/demand-files/public-verification.json"))
    args = parser.parse_args()
    result = verify(args.release, args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "assets": len(result["assets"]), "runtime": result["runtime"]}))
