"""Merge audited local-thunk call contracts into the game configuration."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def format_entries(values, per_line=4):
    lines = []
    for i in range(0, len(values), per_line):
        lines.append("    " + ", ".join("0x%08x" % v for v in values[i:i + per_line]) + ",")
    return "\n".join(lines)


def rewrite_entries(text, entries):
    head, marker, tail = text.partition("entry_points = [")
    if not marker:
        raise ValueError("game.toml has no entry_points list")
    # The closing bracket may share its line with the last address. Brackets
    # inside evidence comments (e.g. CALL [ESI+offset]) are not array ends.
    match = re.search(r"(?m)^[^\n#]*\][ \t]*(?:#[^\n]*)?$", tail)
    if not match:
        raise ValueError("game.toml has no entry_points closing bracket")
    close = match.start() + match.group().index("]")
    return head + marker + "\n" + format_entries(sorted(entries)) + "\n" + tail[close:]


def load_entries(path, identity):
    report = json.loads(path.read_text(encoding="utf-8"))
    if report["executable_sha256"] != identity:
        raise ValueError("Observed entries and contract executable identities differ")
    return [int(value, 0) if isinstance(value, str) else value for value in report["entries"]]


def apply_contracts(game, contracts_path, extra_entries=()):
    report = json.loads(contracts_path.read_text(encoding="utf-8"))
    config_path = game / "game.toml"
    text = config_path.read_text(encoding="utf-8")
    cfg = tomllib.loads(text)
    binary = game / cfg["game"]["developer_exe"]
    identity = cfg["game"]["sha256"]
    if (report["executable_sha256"] != identity
            or hashlib.sha256(binary.read_bytes()).hexdigest() != identity):
        raise ValueError("Contracts and prepared executable identities differ")
    contracts = report["contracts"]
    sites_path = game / cfg["translate"]["no_fallthrough_calls_file"]
    old_sites = set(json.loads(sites_path.read_text(encoding="utf-8")))
    sites = old_sites | {c["call_site"] for c in contracts}
    cont = {c["changed_continuation"] for c in contracts}
    dest = {c["destination"] for c in contracts}
    old_entries = set(cfg["translate"]["entry_points"])
    entries = old_entries | cont | dest | set(extra_entries)
    if any(type(a) is not int or not 0 <= a <= 0xffffffff for a in entries | sites):
        raise ValueError("Entry points and call sites must be 32-bit addresses")
    updated = rewrite_entries(text, entries)
    assert set(tomllib.loads(updated)["translate"]["entry_points"]) == entries
    # Validate everything before changing either input; preserve the first
    # pre-audit state so a repeated application never replaces that backup.
    for path in (config_path, sites_path):
        backup = path.with_name(path.name + ".before-allbytes")
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
    sites_path.write_text(json.dumps(sorted(sites), indent=2) + "\n", encoding="utf-8")
    config_path.write_text(updated, encoding="utf-8")
    return dict(old_sites=len(old_sites), sites=len(sites), old_entries=len(old_entries),
                continuations=len(cont - old_entries),
                destinations=len(dest - old_entries - cont), entries=len(entries))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-dir", type=Path, default=ROOT / "variants/singleplayer")
    ap.add_argument("--contracts", type=Path, default=None)
    ap.add_argument("--entry", action="append", type=lambda value: int(value, 0), default=[],
                    help="Additional independently verified entry address; repeat as needed")
    ap.add_argument("--entries-file", type=Path,
                    help="Same-executable observed entries with an executable_sha256 identity")
    args = ap.parse_args()
    game = args.game_dir.resolve()
    contracts_path = args.contracts or game / "analysis/local-call-thunks-allbytes.json"
    entries = args.entry
    if args.entries_file:
        identity = json.loads(contracts_path.read_text(encoding="utf-8"))["executable_sha256"]
        entries += load_entries(args.entries_file, identity)
    counts = apply_contracts(game, contracts_path, entries)
    print("call sites: %(old_sites)d old -> %(sites)d audited total" % counts)
    print("entries: %(old_entries)d old + %(continuations)d continuations + "
          "%(destinations)d destinations and explicit entries -> %(entries)d total" % counts)


if __name__ == "__main__":
    main()
