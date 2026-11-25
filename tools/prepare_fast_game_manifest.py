"""Index bounded download ranges without changing the existing R2 game objects."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK_SIZE = 4 * 1024 * 1024


def prefetch_list(manifest, trace_path, limit_bytes):
    """Blocks a recorded session read, in first-read order, up to `limit_bytes`.

    The trace is tools/serve_variant.py --range-log output: time, object path,
    offset and size of each served range. Only whole known blocks are kept.
    """
    sizes = {}
    for entry in manifest["entries"]:
        for obj in entry.get("chunks", [entry]):
            sizes[obj["path"]] = obj["size"]
    seen, blocks, total = set(), [], 0
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) != 4:
            continue
        path, offset = fields[1], int(fields[2])
        if path not in sizes or offset % BLOCK_SIZE or offset >= sizes[path] or (path, offset) in seen:
            continue
        size = min(BLOCK_SIZE, sizes[path] - offset)
        if total + size > limit_bytes:
            break
        seen.add((path, offset))
        blocks.append([path, offset])
        total += size
    return blocks, total


def prepare(manifest_path, source, output, trace=None, limit_mb=384):
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
    prefetched = 0
    if trace:
        # Fetched by the demand reader while the game reads nothing, so a new
        # player's first minutes come from the cache instead of waiting.
        manifest["prefetch"], prefetched = prefetch_list(manifest, trace, limit_mb << 20)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"build": manifest["build"], "files": len(manifest["entries"]),
                      "range_blocks": blocks, "block_bytes": BLOCK_SIZE,
                      "prefetch_blocks": len(manifest.get("prefetch", [])),
                      "prefetch_bytes": prefetched}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "variants/singleplayer/prepared")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefetch-trace", type=Path,
                        help="serve_variant.py --range-log of a recorded session")
    parser.add_argument("--prefetch-limit-mb", type=int, default=384)
    args = parser.parse_args()
    prepare(args.manifest, args.source, args.output, args.prefetch_trace, args.prefetch_limit_mb)
