"""Review exclusions without equating a direct-call graph with reachability."""
from pathlib import Path
from bisect import bisect_right
import hashlib
import json
import re
import struct
import tomllib
import pefile

ROOT = Path(__file__).resolve().parents[1]


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    baseline = ROOT / "analysis/curated-core-local"
    current = ROOT / cfg["translate"]["listings"]
    raw = (ROOT / cfg["game"]["developer_exe"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == cfg["game"]["sha256"]
    pe = pefile.PE(data=raw)
    memory = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    def listings(path):
        return {int(p.stem, 16): p for p in (path / "functions").glob("*.asm")}
    old, new = listings(baseline), listings(current)
    removed = sorted(old.keys() - new.keys())
    removed_set = set(removed)
    original_regions = json.loads((baseline / "inline-data.json").read_text())
    regions = json.loads((current / "inline-data.json").read_text())
    added = sorted([r for r in regions if r not in original_regions])
    starts = [r[0] for r in added]
    def excluded(va):
        i = bisect_right(starts, va) - 1
        return i >= 0 and va < added[i][1]
    # These are evidence to inspect, not assertions of a live or dead path.
    refs = []
    pattern = re.compile(r"0x([0-9a-fA-F]{6,8})")
    indirect = 0
    for addr, path in old.items():
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) > 2 and parts[1] in {"CALL", "JMP"}:
                indirect += not bool(re.fullmatch(r"0x[0-9a-fA-F]+", parts[2]))
            for match in pattern.finditer(line):
                target = int(match[1], 16)
                if target in removed_set or excluded(target):
                    refs.append(dict(caller=f"{addr:08x}", caller_retained=addr in new,
                                     target=f"{target:08x}", instruction=line))
    words = []
    for target in removed:
        needle = struct.pack("<I", target)
        pos = memory.find(needle)
        while pos >= 0:
            words.append(dict(target=f"{target:08x}", site=f"{base + pos:08x}"))
            pos = memory.find(needle, pos + 1)
    contract_hits = []
    for contract in json.loads((baseline / "local-call-thunks.json").read_text()).get("contracts", []):
        for name in ("call_site", "callee", "changed_continuation", "destination", "ret4"):
            va = contract[name]
            if va in removed_set or excluded(va):
                contract_hits.append(dict(field=name, address=f"{va:08x}", contract=contract))
    result = dict(source=str(baseline), current=str(current),
                  executable_sha256=cfg["game"]["sha256"],
                  removed_listings=[f"{a:08x}" for a in removed],
                  added_data_regions=added, original_indirect_transfers=indirect,
                  listing_references=refs, original_address_words=words,
                  local_contract_hits=contract_hits,
                  exclusion_safety_proven=False,
                  limitation="A graph of direct transfers omits indirect calls, computed jumps, callbacks and rewritten returns. Address words alone do not prove execution.")
    out = ROOT / "analysis/quarantine-handoff-review.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(dict(removed=len(removed), added_data_regions=len(added),
                         references=len(refs), retained_references=sum(r['caller_retained'] for r in refs),
                         address_words=len(words), indirect_transfers=indirect,
                         contract_hits=len(contract_hits), report=str(out))))


if __name__ == "__main__":
    main()
