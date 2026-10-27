"""Index bounded download ranges without changing the existing R2 game objects."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK_SIZE = 4 * 1024 * 1024


def prepare(manifest_path, source, output):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["rangeBlockSize"] = BLOCK_SIZE
    blocks = 0
    for entry in manifest["entries"]:
        whole = hashlib.sha256()
        with (source / entry["path"]).open("rb") as stream:
            for obj in entry.get("chunks", [entry]):
                obj["ranges"] = []
                object_hash = hashlib.sha256()
                remaining = obj["size"]
                while remaining:
                    data = stream.read(min(remaining, BLOCK_SIZE))
                    if not data:
                        raise ValueError("Prepared source is truncated: " + entry["path"])
                    whole.update(data)
                    object_hash.update(data)
                    obj["ranges"].append(hashlib.sha256(data).hexdigest())
                    remaining -= len(data)
                    blocks += 1
                if object_hash.hexdigest() != obj["sha256"]:
                    raise ValueError("Prepared object differs from inventory: " + obj["path"])
            if stream.read(1) or whole.hexdigest() != entry["sha256"]:
                raise ValueError("Prepared file differs from inventory: " + entry["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"build": manifest["build"], "files": len(manifest["entries"]),
                      "range_blocks": blocks, "block_bytes": BLOCK_SIZE}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "variants/singleplayer/prepared")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.manifest, args.source, args.output)
