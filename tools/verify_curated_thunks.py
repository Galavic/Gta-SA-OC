"""Check curated instructions and original trampoline transfers with Unicorn."""
import argparse
import json
from pathlib import Path
import struct
import sys
import tomllib
import audit_core_data

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EBX, UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_EFLAGS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="analysis/curated-core")
    args = parser.parse_args()
    curated = ROOT / args.input
    image = T.Image(str(ROOT / "original/gta_sa.exe"))
    report = json.loads((curated / "thunk-curation.json").read_text())
    core_data_verified = False
    if (curated / "core-data-check.json").is_file():
        cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
        checked = audit_core_data.verify(ROOT / "original/gta_sa.exe", cfg["game"]["sha256"], ROOT / "analysis/gta_sa.exe")
        if json.loads((curated / "core-data-check.json").read_text()) != checked:
            raise ValueError("Core constant-table provenance differs from original-byte audit")
        if checked["region"] not in json.loads((curated / "inline-data.json").read_text()):
            raise ValueError("Verified constant table is missing from declared data")
        core_data_verified = True
    for repair in report.get("core_repairs", []):
        entry = int(repair["entry"], 16)
        listed = T.parse_listing(str(curated / "functions" / f"{entry:08x}.asm"))
        if repair["reason"] == "empty exported body":
            end = image.insn_end(listed[-1].addr, listed[-1].mnem)
            recovered = image.recover(entry, set(), bounds=(entry, end))
            snapshot = lambda seq: [(i.addr, i.mnem, i.rep, tuple(i.ops)) for i in seq]
            if snapshot(listed) != snapshot(recovered):
                raise ValueError("Repaired core body differs from original instructions")
        elif repair["reason"] == "original CRT INT3 continuation":
            if image.rd8(entry) != 0xCC or len(listed) != 1 or listed[0].addr != entry or listed[0].mnem != "INT3":
                raise ValueError("Repaired CRT continuation differs from original INT3")
        else:
            raise ValueError("Unknown core repair provenance")
    targets = {int(c["target"], 16): c.get("kind", "constant_stack") for c in report["changes"]}
    wrappers_by_function = {}
    for change in report["changes"]:
        target = int(change["target"], 16)
        listed = T.parse_listing(str(curated / "functions" / f"{target:08x}.asm"))
        hi = image.insn_end(listed[-1].addr, listed[-1].mnem)
        wrappers_by_function.setdefault(int(change["entry"], 16), []).append((target - 1, hi))
    # Curation must not remove unrelated paths merely because they cross a
    # section boundary. Every removed start must overlap that body's wrapper.
    for fragment in report.get("split_fragments", []):
        entry = int(fragment["entry"], 16)
        removed = {int(a, 16) for a in fragment["removed_addresses"]}
        if any(not any(lo <= a < hi for lo, hi in wrappers_by_function[entry]) for a in removed):
            raise ValueError("Split fragment falls outside this function's verified wrappers")
        raw = T.parse_listing(str(ROOT / "analysis/gta_sa.exe/functions" / f"{entry:08x}.asm"))
        retained = T.parse_listing(str(curated / "functions" / f"{entry:08x}.asm"))
        expected = [i for i in raw if i.addr not in removed]
        snapshot = lambda seq: [(i.addr, i.mnem, i.rep, tuple(i.ops)) for i in seq]
        if snapshot(retained) != snapshot(expected):
            raise ValueError("Fragment split changed an unrelated instruction")
    emulator = Uc(UC_ARCH_X86, UC_MODE_32)
    emulator.mem_map(image.base, (len(image.data) + 0xFFF) & ~0xFFF)
    emulator.mem_write(image.base, image.data)
    stack, sp = 0x0E000000, 0x0E000800
    emulator.mem_map(stack, 0x1000)
    registers = [UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI]
    for target, kind in sorted(targets.items()):
        fn = curated / "functions" / f"{target:08x}.asm"
        listed = T.parse_listing(str(fn))
        extent = 10 if kind == "call_metadata" else 26
        recovered = image.recover(target, set(), bounds=(target, target + extent))
        snapshot = lambda seq: [(i.addr, i.mnem, i.rep, tuple(i.ops)) for i in seq]
        if snapshot(listed) != snapshot(recovered):
            raise ValueError("Curated instructions differ from original byte recovery")
        if kind == "call_metadata":
            destination = T.parse_imm(listed[1].ops[0])
            words = (target + 10, T.parse_imm(listed[0].ops[0]))
        else:
            values = [T.parse_imm(i.ops[0]) for i in listed[:3]]
            adjustment = T.parse_imm(listed[4].ops[1])
            destination = (values[2] - adjustment) & 0xFFFFFFFF
            words = (values[1], values[0])
        for flags in (0x202, 0xAD7):
            for index, register in enumerate(registers):
                emulator.reg_write(register, 0x11223300 + index)
            emulator.reg_write(UC_X86_REG_ESP, sp)
            emulator.reg_write(UC_X86_REG_EFLAGS, flags)
            emulator.mem_write(sp, struct.pack("<I", 0x01020304))
            emulator.emu_start(target, 0, count=len(listed))
            if emulator.reg_read(UC_X86_REG_EIP) != destination or emulator.reg_read(UC_X86_REG_ESP) != sp - 8:
                raise ValueError("Original trampoline transfer or stack shape differs")
            if emulator.reg_read(UC_X86_REG_EFLAGS) != flags:
                raise ValueError("Original trampoline did not preserve flags")
            if any(emulator.reg_read(r) != 0x11223300 + i for i, r in enumerate(registers)):
                raise ValueError("Original trampoline changed a general register")
            if bytes(emulator.mem_read(sp - 8, 8)) != struct.pack("<II", *words):
                raise ValueError("Original continuation words differ")
    result = dict(original_byte_recovery_identical=True, original_transfers_verified=len(targets), flag_states_per_transfer=2, split_fragment_ownership_verified=len(report.get("split_fragments", [])), core_repairs_verified=len(report.get("core_repairs", [])), translated_execution_verified=False, scope="Original x86 trampoline behavior and curated input identity; not translated C or game execution")
    result["core_constant_table_verified"] = core_data_verified
    (curated / "transfer-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
