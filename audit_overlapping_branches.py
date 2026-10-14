"""Audit original XOR/JZ sequences whose taken target overlaps a listing.

This is a read-only diagnostic, not a CFG rewrite or execution check. An
adjacent XOR of a general register with itself sets ZF; the following JZ
takes its original target. Keep both original instructions in any future
translation and recover that target from its exact bytes.
"""
import hashlib
import json
from pathlib import Path
import sys
import tomllib

import capstone

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    binary = ROOT / cfg["game"]["developer_exe"]
    if hashlib.sha256(binary.read_bytes()).hexdigest() != cfg["game"]["sha256"]:
        raise ValueError("Original executable checksum differs")
    image = T.Image(str(binary))
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    rows = []
    for file in sorted((ROOT / cfg["translate"]["listings"] / "functions").glob("*.asm")):
        listed = T.parse_listing(str(file))
        for instruction, branch in zip(listed, listed[1:]):
            if instruction.mnem != "XOR" or branch.mnem not in ("JZ", "JE"):
                continue
            offset = instruction.addr - image.base
            decoded = list(decoder.disasm(image.data[offset:offset + 16], instruction.addr, count=2))
            if len(decoded) != 2:
                continue
            xor, jump = decoded
            if (xor.mnemonic != "xor" or len(xor.operands) != 2
                    or any(o.type != capstone.CS_OP_REG for o in xor.operands)
                    or xor.operands[0].reg != xor.operands[1].reg
                    or jump.address != branch.addr or jump.mnemonic not in ("je", "jz")
                    or jump.operands[0].type != capstone.CS_OP_IMM):
                continue
            target = jump.operands[0].imm & 0xFFFFFFFF
            covering = next((i for i in listed if i.addr < target < (image.insn_end(i.addr, i.mnem) or i.addr)), None)
            if covering is None:
                continue
            at = target - image.base
            recovered = list(decoder.disasm(image.data[at:at + 32], target, count=4))
            rows.append(dict(function=file.stem, xor=hex(xor.address), branch=hex(jump.address),
                             taken_target=hex(target), overlapping_listing=hex(covering.addr),
                             overlapping_mnemonic=covering.mnem,
                             exact_target_decode=[dict(address=hex(i.address), mnemonic=i.mnemonic, operands=i.op_str) for i in recovered]))
    report = dict(executable_sha256=cfg["game"]["sha256"], source_listings=cfg["translate"]["listings"],
                  original_bytes_modified=False, listings_modified=False,
                  scope="Adjacent original XOR/JZ control flow only; no translated execution or full reachability proof",
                  sites=rows)
    output = ROOT / "analysis/overlapping-branches.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{len(rows)} listed XOR/JZ targets overlap other decoded instructions. Report: {output}")


if __name__ == "__main__":
    main()
