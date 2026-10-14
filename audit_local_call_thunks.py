"""Verify original local stack-call thunks and their changed continuations.

No contract is accepted from bounded execution alone: the entire fixed
straight-line prefix, its sole JMP/RET4 exit, metadata location and original
destination are checked first. Original code and exports remain untouched.
"""
import hashlib
import json
from pathlib import Path
import re
import tomllib

import capstone as C
from capstone.x86_const import X86_REG_ESP

ROOT = Path(__file__).resolve().parent


def stack(op, offset=0):
    return (op.type == C.CS_OP_MEM and op.size == 4 and op.mem.base == X86_REG_ESP
            and op.mem.index == 0 and op.mem.disp == offset)


def inspect(image, site, target):
    # Capstone's linear decode is only used for this fixed ten-instruction
    # form. The JMP's original RET4 target is checked independently.
    raw = image.data[target - image.base:target - image.base + 96]
    if raw[:3] not in (bytes.fromhex("83 04 24"), bytes.fromhex("81 04 24")):
        return None
    decoder = C.Cs(C.CS_ARCH_X86, C.CS_MODE_32)
    decoder.detail = True
    ins = list(decoder.disasm(raw, target, count=10))
    if len(ins) != 10 or [i.mnemonic for i in ins] != ["add", "push", "sub", "push", "xchg", "mov", "add", "xchg", "mov", "jmp"]:
        return None
    a, p, sub, p2, swap, load, add, swap2, write, jump = ins
    if (not stack(a.operands[0]) or a.operands[1].type != C.CS_OP_IMM
            or len(p.operands) != 1 or not stack(p.operands[0])
            or not stack(sub.operands[0]) or sub.operands[1].type != C.CS_OP_IMM
            or len(p2.operands) != 1 or not stack(p2.operands[0])):
        return None
    if not stack(swap.operands[0]) or swap.operands[1].type != C.CS_OP_REG:
        return None
    register = swap.operands[1].reg
    if register == X86_REG_ESP or swap.operands[1].size != 4:
        return None
    if (load.operands[0].type != C.CS_OP_REG or load.operands[0].reg != register
            or load.operands[1].type != C.CS_OP_MEM or load.operands[1].size != 4
            or load.operands[1].mem.base != register or load.operands[1].mem.index
            or load.operands[1].mem.disp != 0
            or add.operands[0].type != C.CS_OP_REG or add.operands[0].reg != register
            or add.operands[1].type != C.CS_OP_IMM
            or not stack(swap2.operands[0]) or swap2.operands[1].type != C.CS_OP_REG
            or swap2.operands[1].reg != register or not stack(write.operands[0], 4)
            or write.operands[1].type != C.CS_OP_IMM or jump.operands[0].type != C.CS_OP_IMM):
        return None
    ret = jump.operands[0].imm & 0xffffffff
    if (ret != write.address + 4 or write.size != 8
            or image.data[ret-image.base:ret-image.base+3] != bytes.fromhex("c2 04 00")):
        return None
    return_word = site + 5
    continuation = (return_word + a.operands[1].imm) & 0xffffffff
    metadata = (continuation - sub.operands[1].imm) & 0xffffffff
    if not (return_word <= metadata and metadata + 4 <= target
            and 0 < continuation - return_word <= 0x1000):
        return None
    encoded = image.rd32(metadata)
    if encoded is None:
        return None
    destination = (encoded + add.operands[1].imm) & 0xffffffff
    end = jump.address + jump.size
    if (destination == return_word or target <= destination < end
            or not image.is_exec(destination) or not image.is_exec(continuation)
            or image.is_declared_data(destination) or image.is_declared_data(continuation)):
        return None
    return dict(call_site=site, callee=target, original_return=return_word,
                changed_continuation=continuation, metadata=metadata,
                destination=destination, end=end, ret4=ret,
                prefix_bytes=image.data[target-image.base:end-image.base].hex(),
                metadata_bytes=image.data[metadata-image.base:metadata-image.base+4].hex())


def audit(cfg, image, directory, checksum=False):
    sites = {}
    for file in sorted((directory / "functions").glob("*.asm")):
        for match in re.finditer(r"^([0-9a-fA-F]+)\s+CALL 0x([0-9a-fA-F]+)\s*$", file.read_text(encoding="utf-8"), re.M):
            site, target = int(match[1], 16), int(match[2], 16)
            if site in sites or not image.is_exec(site) or not image.is_exec(target):
                continue
            at = site - image.base
            code = image.data[at:at+5]
            if len(code) != 5 or code[0] != 0xe8 or (site+5+int.from_bytes(code[1:], "little", signed=True)) & 0xffffffff != target:
                continue
            candidate = inspect(image, site, target)
            if candidate is None and checksum:
                from audit_checksum_call_thunks import inspect as inspect_checksum
                candidate = inspect_checksum(image, site, target)
            if candidate:
                sites[site] = candidate
    result = dict(executable_sha256=cfg["game"]["sha256"], original_bytes_modified=False,
                raw_export_modified=False, contracts=list(sites.values()),
                scope="Fixed original local stack-thunk control/metadata form; translated execution checked separately")
    if checksum:
        result["checksum_forms_included"] = True
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checksum", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "analysis/local-call-thunks.json")
    args = parser.parse_args()
    import sys
    sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
    import translate as T
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    binary = ROOT / cfg["game"]["developer_exe"]
    if hashlib.sha256(binary.read_bytes()).hexdigest() != cfg["game"]["sha256"]:
        raise ValueError("Original executable checksum differs")
    image = T.Image(str(binary))
    regions = cfg["translate"].get("data_regions", []) + json.loads((ROOT / cfg["translate"]["data_regions_file"]).read_text())
    image.declare_data_regions(regions)
    report = audit(cfg, image, ROOT / "analysis/gta_sa.exe", checksum=args.checksum)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Verified {len(report['contracts'])} fixed original local CALL/RET4 forms")


if __name__ == "__main__":
    main()
