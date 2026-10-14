"""Quarantine unreachable strict-build blockers into a fresh curated tree.

Removes the 29 failed listings + 56 listed dangling callers + 2 local-call
prefixes whose verified destinations are quarantined. All removed functions
are unreachable from the entry point and unreferenced by reachable code
(asserted before any write). Originals, raw export and previous curated
trees are left untouched.
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

ROOT = Path(__file__).resolve().parent
ENTRY = 0x00825330


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="analysis/curated-core-dead")
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
    audit = json.loads((ROOT / "analysis/dead-dispatch-audit.json").read_text(encoding="utf-8"))
    if audit["executable_sha256"] != cfg["game"]["sha256"]:
        raise ValueError("Audit targets a different executable identity")
    blk = json.loads((ROOT / "build/recomp/translate-report.blockers.json").read_text(encoding="utf-8"))

    # ---- quarantine set ----
    failed = {int(x["address"], 16) for x in blk["failed_functions"]}
    listed_callers = {int(x["caller"], 16) for x in blk["dangling_dispatch"]
                      if (fdir / f"{x['caller']}.asm").is_file()}
    # prefixes whose verified destination is quarantined (from audit scope)
    contracts = json.loads((src / "local-call-thunks.json").read_text())["contracts"]
    doomed_targets = {c["destination"] for c in contracts} & (failed | listed_callers)
    prefixes = {c["callee"] for c in contracts if c["destination"] in doomed_targets}
    missing_prefix = [f"{a:08x}" for a in prefixes if not (fdir / f"{a:08x}.asm").is_file()]
    if missing_prefix:
        raise ValueError(f"Prefix listings missing: {missing_prefix}")
    print(f"doomed destinations: {[f'{a:08x}' for a in sorted(doomed_targets)]}")
    print(f"prefixes to quarantine: {[f'{a:08x}' for a in sorted(prefixes)]}")
    q = failed | listed_callers | prefixes

    # ---- reachability + safety assertions (before any write) ----
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
    if not q <= fns:
        raise ValueError(f"Quarantine targets without listings: {[f'{a:08x}' for a in q - fns]}")
    seen = {ENTRY}
    queue = deque([ENTRY])
    while queue:
        for target in edges.get(queue.popleft(), ()):
            if target in fns and target not in seen:
                seen.add(target)
                queue.append(target)
    if q & seen:
        raise ValueError(f"Quarantine hits reachable code: {[f'{a:08x}' for a in q & seen]}")
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
    # globals entries naming quarantined addresses
    curated = tomllib.loads((src / "globals.toml").read_text(encoding="utf-8"))
    drop_entries = sorted(name for section, vals in curated.items() if isinstance(vals, dict)
                          for name, val in vals.items() if isinstance(val, int) and val in q)
    print(f"globals entries to drop: {drop_entries}")

    # ---- curate into fresh tree ----
    out = ROOT / args.output
    if out.exists():
        raise ValueError("Use a fresh curation output directory")
    shutil.copytree(src, out)
    records = []
    for addr in sorted(q):
        listing = out / "functions" / f"{addr:08x}.asm"
        digest = hashlib.sha256(listing.read_bytes()).hexdigest()
        listing.unlink()
        reason = ("failed_translation" if addr in failed else
                  "listed_dangling_caller" if addr in listed_callers else "doomed_prefix_destination_quarantined")
        records.append(dict(address=f"{addr:08x}", reason=reason, section=secname(addr),
                            listing_sha256=digest,
                            direct_referrers=sorted(f"{c:08x}" for c in refs.get(addr, ())),
                            reachable_from_entry=False))
    rows = (out / "functions.tsv").read_text(encoding="utf-8").splitlines()
    kept = [rows[0]] + [r for r in rows[1:] if r.strip() and int(r.split("\t")[0], 16) not in q]
    if len(rows) - 1 - (len(kept) - 1) != len(q):
        raise ValueError("functions.tsv row drop count differs from quarantine set")
    (out / "functions.tsv").write_text("\n".join(kept) + "\n", encoding="utf-8")
    text = "# Quarantined unreachable blockers removed; two orphaned local-call targets dropped.\n"
    for section, vals in curated.items():
        text += f"\n[{section}]\n"
        for name, val in sorted(vals.items()):
            if name in drop_entries:
                continue
            text += f"{name} = " + (f"0x{val:08x}" if isinstance(val, int) else json.dumps(val)) + "\n"
    (out / "globals.toml").write_text(text, encoding="utf-8")
    (out / "quarantine.json").write_text(json.dumps(dict(
        executable_sha256=cfg["game"]["sha256"], source_listings=str(src),
        entry=f"{ENTRY:08x}", reachable_listed_functions=len(seen),
        original_bytes_modified=False, raw_export_modified=False,
        removed_functions=len(records), dropped_globals_entries=drop_entries,
        scope="Unreachable strict-build blockers only; no reachable code altered",
        game_execution_verified=False, functions=records), indent=2), encoding="utf-8")
    print(f"Quarantined {len(records)} functions "
          f"({len(failed)} failed, {len(listed_callers)} dangling callers, {len(prefixes)} prefixes); "
          f"dropped {len(drop_entries)} globals entries. Output: {out}")


if __name__ == "__main__":
    main()
