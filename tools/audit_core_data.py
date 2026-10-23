"""Verify the original read-only float table misexported as a GTA function.

Keep every byte available to guest reads; only classify this exact SHA-pinned
constant table as data. This is not a proof of the whole game's control flow.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import tomllib

import capstone
import pefile

ROOT = Path(__file__).resolve().parents[1]
START, END = 0x00859b88, 0x00859b94
EXPECTED = bytes.fromhex("0000003c 0000003f 00008040")


def verify(binary, sha256, listings):
    if hashlib.sha256(binary.read_bytes()).hexdigest() != sha256:
        raise ValueError("Original GTA executable checksum differs")
    pe = pefile.PE(str(binary), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    section = next(s for s in pe.sections if base + s.VirtualAddress <= START
                   and END <= base + s.VirtualAddress + s.Misc_VirtualSize)
    if section.Name.rstrip(b"\0") != b".rdata" or section.Characteristics & 0xa0000000:
        raise ValueError("The constant table is not in original nonexecutable, read-only .rdata")
    if pe.get_data(START - base, END - START) != EXPECTED:
        raise ValueError("Original constant table bytes differ")
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    refs, targets = [], set()
    for file in sorted((listings / "functions").glob("*.asm")):
        text = file.read_text(encoding="utf-8")
        if "859b" not in text.lower():
            continue
        for line in text.splitlines():
            if "859b" not in line.lower():
                continue
            match = re.match(r"([0-9a-fA-F]+)\s+([A-Z0-9]+)\s*(.*)", line)
            if not match:
                continue
            address = int(match[1], 16)
            decoded = list(decoder.disasm(pe.get_data(address - base, 15), address, count=1))
            if not decoded:
                continue
            ins = decoded[0]
            if (ins.mnemonic.startswith("j") or ins.mnemonic.startswith("call")):
                if any(op.type == capstone.CS_OP_IMM and START <= op.imm < END for op in ins.operands):
                    raise ValueError(f"Original direct control flow targets the constant table at {address:x}")
            if not ins.mnemonic.startswith("f") or ins.mnemonic.startswith("fst"):
                continue
            for op in ins.operands:
                if (op.type == capstone.CS_OP_MEM and not op.mem.base and not op.mem.index
                        and START <= op.mem.disp < END and op.size == 4):
                    targets.add(op.mem.disp)
                    refs.append(dict(instruction=hex(address), mnemonic=ins.mnemonic,
                                     constant=hex(op.mem.disp), bytes=bytes(ins.bytes).hex()))
    if targets != set(range(START, END, 4)):
        raise ValueError(f"Constants without original x87 float-read references: {sorted(set(range(START, END, 4)) - targets)}")
    return dict(executable_sha256=sha256, region=[START, END],
                section=".rdata", original_bytes_modified=False,
                original_float_values=list(struct.unpack("<3f", EXPECTED)),
                original_float_read_references=refs,
                direct_control_flow_from_exported_listings_found=False,
                scope="Exact original constant table and original-byte reference checks, not whole-program reachability")


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    report = verify(ROOT / cfg["game"]["developer_exe"], cfg["game"]["sha256"], ROOT / cfg["translate"]["listings"])
    (ROOT / "analysis/core-data-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Verified 3 original float constants and {len(report['original_float_read_references'])} original x87 reads; bytes unchanged")


if __name__ == "__main__":
    main()
