"""Read-only audit of the 204 dangling dispatches + 29 failed functions.

Verifies every claim against original bytes with capstone; modifies nothing.
Findings go to analysis/dead-dispatch-audit.json.
"""
import hashlib
import json
import re
from pathlib import Path
import sys
import tomllib
from collections import defaultdict, deque

import capstone
import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T

ENTRY = 0x00825330


def sections(pe, base):
    out = []
    for s in pe.sections:
        name = s.Name.rstrip(b"\0").decode("ascii", "replace")
        va = base + s.VirtualAddress
        out.append(dict(name=name, start=va, end=va + max(s.Misc_VirtualSize, s.SizeOfRawData),
                        exec=bool(s.Characteristics & 0x20000000)))
    return out


def sec_of(sections, va):
    for s in sections:
        if s["start"] <= va < s["end"]:
            return s["name"], s["exec"]
    return None, False


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    binary = ROOT / cfg["game"]["developer_exe"]
    raw = binary.read_bytes()
    if hashlib.sha256(raw).hexdigest() != cfg["game"]["sha256"]:
        raise ValueError("Original executable checksum differs")
    pe = pefile.PE(data=raw)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    secs = sections(pe, base)
    src = ROOT / cfg["translate"]["listings"]
    fdir = src / "functions"
    blk = json.loads((ROOT / "build/recomp/translate-report.blockers.json").read_text(encoding="utf-8"))

    dec = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    dec.detail = True

    def at(va, n=16):
        return bytes(image[va - base:va - base + n])

    # ---- direct-transfer graph from listings (CALL + JMP + JCC) ----
    call_re = re.compile(r"^([0-9a-fA-F]+)\s+([A-Z]+)\s*(.*)$")
    JMPS = {"JMP", "JZ", "JE", "JNZ", "JNE", "JB", "JAE", "JA", "JBE", "JG", "JGE",
            "JL", "JLE", "JO", "JNO", "JS", "JNS", "JP", "JNP", "JCXZ", "JECXZ",
            "LOOP", "LOOPE", "LOOPNE"}
    edges = defaultdict(set)
    listing_fns = set()
    for p in fdir.glob("*.asm"):
        try:
            fn = int(p.stem, 16)
        except ValueError:
            continue
        listing_fns.add(fn)
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            m = call_re.match(line)
            if not m:
                continue
            mnem, ops = m.group(2), m.group(3)
            if mnem in ({"CALL"} | JMPS):
                m2 = re.search(r"0x([0-9a-fA-F]+)", ops)
                if m2:
                    edges[fn].add(int(m2.group(1), 16))
    seen = {ENTRY}
    queue = deque([ENTRY])
    while queue:
        for target in edges.get(queue.popleft(), ()):
            if target in listing_fns and target not in seen:
                seen.add(target)
                queue.append(target)
    reachable = seen

    # ---- classify dangling ----
    failed = {x["address"] for x in blk["failed_functions"]}
    rows = []
    for item in blk["dangling_dispatch"]:
        caller = int(item["caller"], 16)
        target = int(item["target"], 16)
        rec = dict(caller=item["caller"], target=item["target"], line=item["line"][:120],
                   caller_has_listing=(caller in listing_fns),
                   target_has_listing=(target in listing_fns),
                   caller_reachable=caller in reachable,
                   target_in_image=base <= target < base + len(image))
        sec, is_exec = sec_of(secs, target)
        rec["target_section"] = sec
        rec["target_section_exec"] = is_exec
        rec["target_is_failed_fn"] = item["target"] in failed
        # locate the dispatch site in the caller listing (if any) and verify bytes
        site = None
        if caller in listing_fns:
            for line in (fdir / f"{caller:08x}.asm").read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] in ("CALL", "JMP") and f"{target:08x}" in line.lower():
                    try:
                        site = int(parts[0], 16)
                        break
                    except ValueError:
                        pass
        rec["site_in_listing"] = f"{site:08x}" if site is not None else None
        if site is not None:
            insns = list(dec.disasm(at(site), site, count=1))
            if insns:
                ins = insns[0]
                rec["site_bytes_mnemonic"] = ins.mnemonic
                rec["site_bytes_ops"] = ins.op_str
                rec["site_bytes_size"] = ins.size
                if ins.mnemonic == "call" and ins.operands and ins.operands[0].type == capstone.CS_OP_IMM:
                    rec["site_bytes_target"] = f"{ins.operands[0].imm & 0xFFFFFFFF:08x}"
                # dead shadow: exact bytes of two previous listing instructions
                lines = (fdir / f"{caller:08x}.asm").read_text(encoding="utf-8", errors="replace").splitlines()
                addrs = []
                for line in lines:
                    parts = line.strip().split()
                    if parts:
                        try:
                            addrs.append(int(parts[0], 16))
                        except ValueError:
                            pass
                if site in addrs:
                    idx = addrs.index(site)
                    prev = addrs[max(0, idx - 2):idx]
                    if len(prev) == 2:
                        raw_prev = list(dec.disasm(at(prev[0], 16), prev[0], count=2))
                        if (len(raw_prev) == 2 and raw_prev[0].mnemonic == "xor"
                                and len(raw_prev[0].operands) == 2
                                and all(o.type == capstone.CS_OP_REG for o in raw_prev[0].operands)
                                and raw_prev[0].operands[0].reg == raw_prev[0].operands[1].reg
                                and raw_prev[1].mnemonic in ("je", "jz")
                                and raw_prev[1].operands[0].type == capstone.CS_OP_IMM
                                and (raw_prev[1].operands[0].imm & 0xFFFFFFFF) > site):
                            rec["dead_shadow_bytes_verified"] = True
                            rec["dead_shadow"] = [f"{raw_prev[0].address:08x} {raw_prev[0].mnemonic} {raw_prev[0].op_str}",
                                                  f"{raw_prev[1].address:08x} {raw_prev[1].mnemonic} {raw_prev[1].op_str}"]
                        else:
                            rec["dead_shadow_bytes_verified"] = False
                    else:
                        rec["dead_shadow_bytes_verified"] = False
                else:
                    rec["dead_shadow_bytes_verified"] = False
        rows.append(rec)

    # ---- failed functions ----
    frecs = []
    for item in blk["failed_functions"]:
        addr = int(item["address"], 16)
        sec, is_exec = sec_of(secs, addr)
        refs = sorted(f"{c:08x}" for c in edges if addr in edges[c])
        live_refs = [c for c in refs if int(c, 16) in reachable]
        # decode failing instruction bytes
        fail_addr = None
        m = re.match(r"([0-9a-fA-F]+)\s+(\S+)", item["error"])
        if m:
            fail_addr = int(m.group(1), 16)
        fail_decode = None
        if fail_addr is not None and base <= fail_addr < base + len(image):
            insns = list(dec.disasm(at(fail_addr), fail_addr, count=1))
            if insns:
                fail_decode = f"{insns[0].mnemonic} {insns[0].op_str} size={insns[0].size}"
        frecs.append(dict(address=item["address"], error=item["error"][:160],
                          section=sec, section_exec=is_exec,
                          has_listing=addr in listing_fns,
                          reachable_from_entry=addr in reachable,
                          direct_referrers=refs, live_referrers=live_refs,
                          failing_bytes_decode=fail_decode))

    # ---- seed hunt for discovered-only junk callers (0xE6 cluster etc.) ----
    discovered = sorted({int(x["caller"], 16) for x in blk["dangling_dispatch"]} - listing_fns)
    seeds = []
    if discovered:
        lo, hi = min(discovered), max(discovered)
        # dwords in image pointing into [lo, hi]
        import struct
        ptrs = []
        for off in range(0, len(image) - 4):
            val = struct.unpack_from("<I", image, off)[0]
            if lo <= val <= hi:
                ptrs.append((base + off, val))
                if len(ptrs) >= 40:
                    break
        for loc, val in ptrs[:40]:
            sname, _ = sec_of(secs, loc)
            seeds.append(dict(pointer_location=f"{loc:08x}", points_to=f"{val:08x}", section=sname))

    report = dict(executable_sha256=cfg["game"]["sha256"], entry=f"{ENTRY:08x}",
                  listings=str(src), reachable_listed_functions=len(reachable),
                  listed_functions=len(listing_fns),
                  dangling_total=len(rows),
                  dangling_callers_listed=sum(1 for r in rows if r["caller_has_listing"]),
                  dangling_outside_image=sum(1 for r in rows if not r["target_in_image"]),
                  dangling_dead_shadow_verified=sum(1 for r in rows if r.get("dead_shadow_bytes_verified")),
                  dangling_to_failed=sum(1 for r in rows if r["target_is_failed_fn"]),
                  failed_total=len(frecs),
                  failed_reachable=sum(1 for f in frecs if f["reachable_from_entry"]),
                  original_bytes_modified=False, listings_modified=False,
                  scope="Byte-verified classification of current strict-build blockers; no translation or execution claims",
                  dangling=rows, failed=frecs, junk_seeds_sample=seeds)
    out = ROOT / "analysis/dead-dispatch-audit.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("dangling_total", "dangling_callers_listed", "dangling_outside_image",
                                            "dangling_dead_shadow_verified", "dangling_to_failed",
                                            "failed_total", "failed_reachable",
                                            "reachable_listed_functions", "listed_functions")}, indent=2))
    print("junk pointer seeds found:", len(seeds))


if __name__ == "__main__":
    main()
