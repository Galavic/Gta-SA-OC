"""Round 3: quarantine listed dangling callers + overlapping fragments, declare
orphan-body spans (kit's own recovery) as data. All removed/declared bytes
are unreachable from the entry and unreferenced by reachable code (asserted
before any write). Chains on game.toml listings (dead2 -> dead3)."""
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
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T

ENTRY = 0x00825330


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--spans", default=str(Path.home() / "AppData/Local/Temp/clyra/spans1.json"))
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
        raise ValueError("Failed functions present; handle before span round")

    # ---- graph + reachability ----
    call_re = re.compile(r"^([0-9a-fA-F]+)\s+([A-Z]+)\s*(.*)$")
    jmps = {"JMP", "JZ", "JE", "JNZ", "JNE", "JB", "JAE", "JA", "JBE", "JG", "JGE",
            "JL", "JLE", "JO", "JNO", "JS", "JNS", "JP", "JNP", "JCXZ", "JECXZ",
            "LOOP", "LOOPE", "LOOPNE"}
    edges = defaultdict(set)
    fns = set()
    texts = {}
    insn_end = {}
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
            a = int(m.group(1), 16)
            insn_end[a] = max(insn_end.get(a, 0), a + 1)
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

    # ---- quarantine seeds: listed dangling callers ----
    seeds = {int(x["caller"], 16) for x in blk.get("dangling_dispatch", [])
             if (fdir / f"{x['caller']}.asm").is_file()}
    print("listed dangling-caller seeds:", sorted(f"{a:08x}" for a in seeds))

    # ---- spans ----
    raw_spans = [(int(s["lo"], 16), int(s["hi"], 16)) for s in json.loads(Path(args.spans).read_text())]
    # drop spans fully inside already-declared data
    declared = [tuple(r) for r in cfg["translate"].get("data_regions", [])] + \
               [tuple(r) for r in json.loads((ROOT / cfg["translate"]["data_regions_file"]).read_text())]
    def covered(lo, hi):
        return any(dlo <= lo and hi <= dhi for dlo, dhi in declared)
    spans = sorted((lo, hi) for lo, hi in raw_spans if not covered(lo, hi))
    print(f"spans: {len(raw_spans)} raw, {len(spans)} after declared-data filter")

    # ---- overlapping listed functions join the quarantine ----
    overlap = set()
    for lo, hi in spans:
        for fn, text in texts.items():
            for line in text.splitlines():
                m = call_re.match(line.strip())
                if m and lo <= int(m.group(1), 16) < hi:
                    overlap.add(fn)
                    break
    print("listed fns overlapping spans:", sorted(f"{a:08x}" for a in overlap))

    q = set(seeds) | overlap
    frontier = list(q)
    while frontier:
        cur = frontier.pop(0)
        for c, ts in edges.items():
            if cur in ts and c not in q:
                if c in seen:
                    raise ValueError(f"Closure reaches reachable code at {c:08x}; aborting")
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
    # spans must contain no reachable insn
    reach_insns = set()
    for fn in seen:
        for line in texts[fn].splitlines():
            m = call_re.match(line.strip())
            if m:
                reach_insns.add(int(m.group(1), 16))
    for lo, hi in spans:
        hit = [x for x in reach_insns if lo <= x < hi]
        if hit:
            raise ValueError(f"Span {lo:08x}-{hi:08x} hits reachable code; aborting")
    # expand spans over quarantined overlap members' full byte ranges
    fn_maxend = {}
    for fn in overlap:
        ends = []
        for line in texts[fn].splitlines():
            m = call_re.match(line.strip())
            if m:
                ends.append(int(m.group(1), 16) + 1)
        fn_maxend[fn] = max(ends) if ends else fn + 1
    expanded = []
    for lo, hi in spans:
        for fn in overlap:
            fstart = min(int(call_re.match(l.strip()).group(1), 16)
                         for l in texts[fn].splitlines() if call_re.match(l.strip()))
            if lo <= fstart < hi:
                hi = max(hi, fn_maxend[fn])
        expanded.append((lo, hi))
    # merge overlapping expanded spans
    expanded.sort()
    merged = []
    for lo, hi in expanded:
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    print(f"data spans to declare: {len(merged)}, bytes: {sum(hi - lo for lo, hi in merged)}")

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
        records.append(dict(address=f"{addr:08x}", reason="round3_dangling_closure_or_span_overlap",
                            section=secname(addr), listing_sha256=digest,
                            direct_referrers=sorted(f"{c:08x}" for c in refs.get(addr, ())),
                            reachable_from_entry=False))
    rows = (out / "functions.tsv").read_text(encoding="utf-8").splitlines()
    kept = [rows[0]] + [r for r in rows[1:] if r.strip() and int(r.split("\t")[0], 16) not in q]
    if len(rows) - 1 - (len(kept) - 1) != len(q):
        raise ValueError("functions.tsv row drop count differs from quarantine set")
    (out / "functions.tsv").write_text("\n".join(kept) + "\n", encoding="utf-8")
    text = "# Round 3: unreachable dangling closure + span-overlap fragments removed.\n"
    for section, vals in curated.items():
        text += f"\n[{section}]\n"
        for name, val in sorted(vals.items()):
            if name in drop_entries:
                continue
            text += f"{name} = " + (f"0x{val:08x}" if isinstance(val, int) else json.dumps(val)) + "\n"
    (out / "globals.toml").write_text(text, encoding="utf-8")
    data = sorted([list(r) for r in json.loads((out / "inline-data.json").read_text())] + [[lo, hi] for lo, hi in merged])
    # merge adjacent data ranges
    data.sort()
    mg = []
    for lo, hi in data:
        if mg and lo <= mg[-1][1]:
            mg[-1][1] = max(mg[-1][1], hi)
        else:
            mg.append([lo, hi])
    (out / "inline-data.json").write_text(json.dumps(mg), encoding="utf-8")
    prev_q = []
    pq = src / "quarantine.json"
    if pq.is_file():
        prev_q = json.loads(pq.read_text(encoding="utf-8")).get("previous", []) + \
                 json.loads(pq.read_text(encoding="utf-8")).get("functions", [])
    (out / "quarantine.json").write_text(json.dumps(dict(
        executable_sha256=cfg["game"]["sha256"], source_listings=str(src),
        entry=f"{ENTRY:08x}", reachable_listed_functions=len(seen),
        original_bytes_modified=False, raw_export_modified=False,
        removed_functions_round=len(records), data_spans_declared=len(merged),
        data_spans=merged,
        dropped_globals_entries=drop_entries,
        scope="Unreachable dangling closure + orphan-body data spans; no reachable code altered",
        game_execution_verified=False,
        previous=prev_q, functions=records), indent=2, default=str), encoding="utf-8")
    print(f"Quarantined {len(records)} more; declared {len(merged)} spans. Output: {out}")


if __name__ == "__main__":
    main()
