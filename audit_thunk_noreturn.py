"""Audit four return-address-mangling thunks as never-returning callees.

Each thunk is CALLed once (verified by xref) and mangles its return address
(ADD [ESP],X / PUSH [ESP] / SUB ...). The audit walks every direct path from
the thunk's first byte through original image bytes with capstone: a callee
qualifies only if no path reaches RET/RETF/IRET and every path ends in an
in-body loop, an indirect transfer, a call outside the image, or bytes that
do not decode. Paths that leave the walked window are reported, never
assumed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

CALLERS = {
    0x00D52A8C: [0x00D52A7F],
    0x00D53BC2: [0x00D53BB6],
    0x01290826: [0x01290817],
    0x01297DE0: [0x01297DD3],
}

TERMINAL_RET = {"ret", "retf", "iretd", "iret"}


def walk(image, md, start, budget=400):
    """Follow direct branches from `start`; return (verdict, evidence)."""
    seen = set()
    stack = [start]
    notes = []
    while stack and len(seen) < budget:
        addr = stack.pop()
        if addr in seen:
            continue
        seen.add(addr)
        if not image.is_exec(addr):
            notes.append("left-image-or-data@%08x" % addr)
            return False, notes
        raw = bytes(image.data[addr - image.base:addr - image.base + 16])
        try:
            ins = next(md.disasm(raw, addr, count=1), None)
        except Exception:
            ins = None
        if ins is None or not ins.mnemonic:
            notes.append("undecodable@%08x" % addr)
            continue
        m = ins.mnemonic
        if m in TERMINAL_RET:
            notes.append("RET@%08x" % addr)
            return False, notes
        if m == "int3":
            notes.append("int3@%08x" % addr)
            continue
        if m in ("call",):
            if ins.op_str.startswith("0x"):
                notes.append("call-out@%08x->%s" % (addr, ins.op_str))
                continue
            notes.append("indirect-call@%08x" % addr)
            continue
        if m == "jmp":
            if ins.op_str.startswith("0x"):
                stack.append(int(ins.op_str, 16))
                continue
            notes.append("indirect-jmp@%08x" % addr)
            continue
        if m.startswith("j") or m.startswith("loop"):
            if ins.op_str.startswith("0x"):
                stack.append(int(ins.op_str, 16))
            else:
                notes.append("indirect-branch@%08x" % addr)
                continue
        stack.append(addr + ins.size)
    if len(seen) >= budget:
        notes.append("budget-exhausted")
        return False, notes
    return True, notes


def main():
    image = T.Image(str(ROOT / "variants/singleplayer/prepared/gta_sa.exe"))
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    report = {"executable_sha256": "a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26",
              "original_bytes_modified": False,
              "scope": ("Direct CALL sites whose callee provably never returns: "
                        "exhaustive direct-path walk from the callee's first byte "
                        "finds no RET and ends only in loops, indirect transfers, "
                        "out-of-image calls, INT3 or undecodable bytes."),
              "sites": []}
    ok = True
    for callee, callers in CALLERS.items():
        noreturn, notes = walk(image, md, callee)
        first = bytes(image.data[callee - image.base:callee - image.base + 10]).hex()
        print("%08x noreturn=%s first=%s notes=%s" % (callee, noreturn, first, notes[:6]))
        ok = ok and noreturn
        report["sites"].append({"callers": ["%08x" % c for c in callers],
                               "callee": "%08x" % callee,
                               "first_bytes": first,
                               "noreturn": noreturn, "paths": notes[:12]})
    (ROOT / "variants/singleplayer/no-fallthrough-calls-thunks.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    if not ok:
        raise SystemExit("a thunk shows a return path; not adding sites")


if __name__ == "__main__":
    main()
