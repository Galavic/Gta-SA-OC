"""Repair one truncated exported body from the pinned original native CFG.

This preserves the original image and all other exported entries. It is a
listing repair, not evidence of whole-game execution or callback reachability.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    directory = args.input.resolve()
    if directory.parent != (ROOT / "analysis").resolve():
        raise ValueError("Repair only a project analysis directory")
    cfg = tomllib.loads((ROOT / "game.toml").read_text())
    binary = ROOT / cfg["game"]["developer_exe"]
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    if digest != cfg["game"]["sha256"]:
        raise ValueError("Original executable changed")
    image = T.Image(str(binary))
    start, end = 0xF1211A, 0xF1223C
    rows = (directory / "functions.tsv").read_text().splitlines()
    indexed = {int(row.split("\t")[0], 16): row.split("\t") for row in rows[1:]}
    if end not in indexed or any(start < a < end for a in indexed):
        raise ValueError("Canonical body overlaps another exported entry")
    body = image.recover(start, set(), bounds=(start, end))
    if len(body) != 131 or body[-1].addr != end - 1 or body[-1].mnem != "RET":
        raise ValueError("Pinned original native CFG differs")
    canonical = {i.addr for i in body}
    listing = directory / "functions" / f"{start:08x}.asm"
    old = listing.read_text()
    pseudo = sorted(i.addr for i in T.parse_listing(str(listing)) if i.addr not in canonical)
    if pseudo != [0xF121E0, 0xF121E6, 0xF121EA]:
        raise ValueError("Unexpected old overlapping instruction boundaries")
    # Check actual immediate control-flow operands, rather than trusting the
    # exported mnemonic or counting pointers as executed branch targets.
    direct_refs = []
    for path in (directory / "functions").glob("*.asm"):
        for line in path.read_text().splitlines():
            if not any(f"{a:06x}" in line.lower() for a in pseudo):
                continue
            address = int(line.split()[0], 16)
            ci = next(image.md.disasm(image.data[address-image.base:address-image.base+16], address, count=1), None)
            if ci is None:
                continue
            if ci.mnemonic.startswith(("j", "loop")) or ci.mnemonic == "call":
                if any(op.type == 2 and op.imm in pseudo for op in ci.operands):
                    direct_refs.append(dict(source=f"{address:08x}", listing=path.name))
    if direct_refs:
        raise ValueError(f"Original direct branches enter pseudo-boundaries: {direct_refs}")
    # One PUSH contains f121e0, but the real stack trampoline subtracts
    # 16b10 before RET. Preserve this listing and report its actual target.
    trampoline = image.recover(0x150E8A0, set(), bounds=(0x150E8A0, 0x150E8BA))
    expected = [("PUSH", ["0x150e8ba"]), ("PUSH", ["0x4034e0"]),
                ("PUSH", ["0xf121e0"]), ("PUSHFD", []),
                ("SUB", ["dword ptr [ESP + 0x4]", "0x16b10"]),
                ("POPFD", []), ("RET", [])]
    if [(i.mnem, i.ops) for i in trampoline] != expected:
        raise ValueError("Original pointer trampoline differs")
    report_path = directory / "f1211a-native-body-repair.json"
    if report_path.exists():
        raise ValueError("Already repaired; use a fresh analysis tree")
    new = "\n".join(f"{i.addr:08x}  {i.mnem} {','.join(i.ops)}".rstrip() for i in body) + "\n"
    report = dict(original_executable_sha256=digest, address=f"{start:08x}",
                  end=f"{end:08x}", native_instructions=len(body),
                  removed_pseudo_boundaries=[f"{a:08x}" for a in pseudo],
                  original_direct_refs_to_removed_boundaries=direct_refs,
                  pointer_trampoline=dict(address="0150e8a0", pushed="00f121e0",
                                          subtract="00016b10", actual_return="00efb6d0"),
                  original_listing=old, canonical_listing_sha256=hashlib.sha256(new.encode()).hexdigest(),
                  game_execution_verified=False,
                  scope="Pinned native recursive-descent CFG; indirect entry reachability is not proven")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    indexed[start][2] = str(end-start)
    listing.write_text(new, encoding="utf-8")
    (directory / "functions.tsv").write_text(rows[0]+"\n"+"\n".join("\t".join(indexed[a]) for a in sorted(indexed))+"\n", encoding="utf-8")
    print(f"Repaired {start:08x}: {len(body)} original instructions, ending at {end:08x}; original bytes unchanged")


if __name__ == "__main__":
    main()
