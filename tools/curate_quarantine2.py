"""Second quarantine round: listed dangling callers of the current build + closure.

Same safety contract as round 1: everything removed is unreachable from the
entry and unreferenced by reachable code (asserted before any write).
Reads game.toml listings as source so it chains (dead1 -> dead2).
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import tomllib
from collections import defaultdict, deque
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
ENTRY = 0x00825330


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    binary = ROOT / cfg["game"]["developer_exe"]
    raw = binary.read_bytes()
    if hashlib.sha256(raw).hexdigest() != cfg["game"]["sha256"]:
        raise ValueError("Original executable checksum differs")
    pe = pefile.PE(data=raw)
    base = pe.OPTIONAL_HEADER.ImageBase

    def secname(va):
        for s in pe.sections:
            if base + s.VirtualAddress <= va < base + s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
                return s.Name.rstrip(b"\0").decode("ascii", "replace")
        return None

    src = ROOT / cfg["translate"]["listings"]
    fdir = src / "functions"
    blk = json.loads((ROOT / "build/recomp/translate-report.blockers.json").read_text(encoding="utf-8"))
    if blk.get("failed_functions"):
        print("WARNING: failed functions present:", len(blk["failed_functions"]))

    call_re = re.compile(r"^([0-9a-fA-F]+)\s+([A-Z]+)\s*(.*)$")
    jmps = {"JMP", "JZ", "JE", "JNZ", "JNE", "JB", "JAE", "JA", "JBE", "JG", "JGE",
            "JL", "JLE", "JO", "JNO", "JS", "JNS", "JP", "JNP", "JCXZ", "JECXZ",
            "LOOP", "LOOPE", "LOOPNE"}
    edges = defaultdict(set)
    fns = set()
    texts = {}
    for p in fdir.glob("*.asm"):
        try:
            fn = int(p.stem, 16)
        except ValueError:
            continue
        fns.add(fn)
        text = p.read_text(encoding="utf-8", errors="replace")
        texts[fn] = text
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = call_re.match(line)
            if not m:
                continue
            if m.group(2) in ({"CALL"} | jmps):
                m2 = re.search(r"0x([0-9a-fA-F]+)", m.group(3))
                if m2:
                    edges[fn].add(int(m2.group(1), 16))
    seen = {ENTRY}
    queue = deque([ENTRY])
    while queue:
        for target in edges.get(queue.popleft(), ()):
            if target in fns and target not in seen:
                seen.add(target)
                queue.append(target)

    seeds = {int(x["caller"], 16) for x in blk.get("dangling_dispatch", [])
             if (fdir / f"{x['caller']}.asm").is_file()}
    print("listed dangling-caller seeds:", len(seeds))
    # closure over referrers while unreachable
    q = set(seeds)
    frontier = list(seeds)
    while frontier:
        referrers = [c for c, ts in edges.items() if (ts & {frontier[0]}) and c not in q]
        frontier.pop(0)
        for c in referrers:
            if c in seen:
                raise ValueError(f"Closure reaches reachable code at {c:08x}; aborting")
            if c not in q:
                q.add(c)
                frontier.append(c)
    print("quarantine closure size:", len(q))
    if q & seen:
        raise ValueError("Quarantine hits reachable code")
    refs = defaultdict(set)
    for caller, targets in edges.items():
        for target in targets & q:
            refs[target].add(caller)
    live_refs = sorted({c for s in refs.values() for c in s} & seen)
    if live_refs:
        raise ValueError(f"Reachable code references quarantine: {[f'{a:08x}' for a in live_refs]}")
    hexpat = re.compile(r"0x([0-9a-f]{6,8})")
    mentioning = sorted(fn for fn in seen
                        if any(int(m.group(1), 16) in q for m in hexpat.finditer(texts[fn].lower())))
    if mentioning:
        raise ValueError(f"Reachable listings mention quarantine: {[f'{a:08x}' for a in mentioning]}")
    curated = tomllib.loads((src / "globals.toml").read_text(encoding="utf-8"))
    drop_entries = sorted(name for section, vals in curated.items() if isinstance(vals, dict)
                          for name, val in vals.items() if isinstance(val, int) and val in q)
    print("globals entries to drop:", drop_entries)

    out = ROOT / args.output
    if out.exists():
        raise ValueError("Use a fresh curation output directory")
    shutil.copytree(src, out)
    records = []
    for addr in sorted(q):
        listing = out / "functions" / f"{addr:08x}.asm"
        digest = hashlib.sha256(listing.read_bytes()).hexdigest()
        listing.unlink()
        records.append(dict(address=f"{addr:08x}", reason="listed_dangling_caller_closure",
                            section=secname(addr), listing_sha256=digest,
                            direct_referrers=sorted(f"{c:08x}" for c in refs.get(addr, ())),
                            reachable_from_entry=False))
    rows = (out / "functions.tsv").read_text(encoding="utf-8").splitlines()
    kept = [rows[0]] + [r for r in rows[1:] if r.strip() and int(r.split("\t")[0], 16) not in q]
    if len(rows) - 1 - (len(kept) - 1) != len(q):
        raise ValueError("functions.tsv row drop count differs from quarantine set")
    (out / "functions.tsv").write_text("\n".join(kept) + "\n", encoding="utf-8")
    text = "# Quarantine round 2: unreachable listed dangling callers removed.\n"
    for section, vals in curated.items():
        text += f"\n[{section}]\n"
        for name, val in sorted(vals.items()):
            if name in drop_entries:
                continue
            text += f"{name} = " + (f"0x{val:08x}" if isinstance(val, int) else json.dumps(val)) + "\n"
    (out / "globals.toml").write_text(text, encoding="utf-8")
    prev_q = []
    pq = src / "quarantine.json"
    if pq.is_file():
        prev_q = json.loads(pq.read_text(encoding="utf-8"))["functions"]
    (out / "quarantine.json").write_text(json.dumps(dict(
        executable_sha256=cfg["game"]["sha256"], source_listings=str(src),
        entry=f"{ENTRY:08x}", reachable_listed_functions=len(seen),
        original_bytes_modified=False, raw_export_modified=False,
        removed_functions_round=len(records), removed_functions_total=len(prev_q) + len(records),
        dropped_globals_entries=drop_entries,
        scope="Unreachable listed dangling callers + referrer closure; no reachable code altered",
        game_execution_verified=False,
        previous=prev_q, functions=records), indent=2), encoding="utf-8")
    print(f"Quarantined {len(records)} more functions. Output: {out}")


if __name__ == "__main__":
    main()
