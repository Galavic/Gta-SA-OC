"""Merge audited local-thunk call contracts into the game configuration."""
import argparse
import json
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parent


def format_entries(values, per_line=4):
    lines = []
    for i in range(0, len(values), per_line):
        lines.append("    " + ", ".join("0x%08x" % v for v in values[i:i + per_line]) + ",")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-dir", type=Path, default=ROOT / "variants/singleplayer")
    ap.add_argument("--contracts", type=Path, default=None)
    args = ap.parse_args()
    game = args.game_dir.resolve()
    contracts_path = args.contracts or game / "analysis/local-call-thunks-allbytes.json"
    contracts = json.loads(contracts_path.read_text())["contracts"]
    cfg = tomllib.loads((game / "game.toml").read_text(encoding="utf-8"))

    old_sites = set(json.loads((game / "no-fallthrough-calls.json").read_text()))
    sites = old_sites | {c["call_site"] for c in contracts}
    cont = {c["changed_continuation"] for c in contracts}
    dest = {c["destination"] for c in contracts}
    old_entries = set(cfg["translate"]["entry_points"])
    entries = old_entries | cont | dest

    (game / "no-fallthrough-calls.json.before-allbytes").write_text(
        json.dumps(sorted(old_sites), indent=2) + "\n")
    (game / "no-fallthrough-calls.json").write_text(
        json.dumps(sorted(sites), indent=2) + "\n")

    text = (game / "game.toml").read_text(encoding="utf-8")
    head, marker, tail = text.partition("entry_points = [")
    if not marker:
        raise SystemExit("game.toml has no entry_points list")
    close = tail.index("\n]")
    body = format_entries(sorted(entries))
    text = head + marker + "\n" + body + tail[close:]
    (game / "game.toml.before-allbytes").write_text(
        (game / "game.toml").read_text(encoding="utf-8"))
    (game / "game.toml").write_text(text, encoding="utf-8")

    print("call sites: %d old + %d new = %d" % (len(old_sites), len(sites) - len(old_sites), len(sites)))
    print("entries: %d old + %d continuations + %d destinations = %d"
          % (len(old_entries), len(cont - old_entries), len(dest - old_entries - cont), len(entries)))


if __name__ == "__main__":
    main()
