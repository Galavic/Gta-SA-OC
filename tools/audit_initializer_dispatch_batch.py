"""Bound table wrapper transfers in dumped memory, stopping before constructors.

Only MOV ECX,imm / CALL literal wrappers whose callee is an absolute indirect
JMP to the verified 26-byte stack dispatcher form are executed. Each case
restores touched memory pages and CPU state. No constructor/import is run.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from types import SimpleNamespace

import pefile
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import *

from audit_boot_snapshot import descriptor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def main():
    directory = ROOT / "build/boot-probe-current"
    state = json.loads((directory / "halt.json").read_text())
    executable = ROOT / "prepared/gta_sa.exe"
    sha = hashlib.sha256(executable.read_bytes()).hexdigest()
    assert sha == state["exe_sha256"]
    pe = pefile.PE(str(executable))
    original = pe.get_memory_mapped_image()
    image_base = pe.OPTIONAL_HEADER.ImageBase
    regions = [(r["base"], (directory / ("halt" + r["suffix"])).read_bytes()) for r in state["regions"]]
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    for base, raw in regions:
        u.mem_map(base, (len(raw) + 4095) & ~4095)
        u.mem_write(base, raw)
    gdt = 0x20000000
    u.mem_map(gdt, 4096)
    u.mem_write(gdt, b"\0" * 8 + descriptor(0, access=0x9B) + descriptor(0) + descriptor(state["fs_base"]))
    u.reg_write(UC_X86_REG_GDTR, (0, gdt, 31, 0))
    u.reg_write(UC_X86_REG_CS, 8)
    for reg in (UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS):
        u.reg_write(reg, 16)
    u.reg_write(UC_X86_REG_FS, 24)
    regs = (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EBX,
            UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI)
    header = (ROOT / "build/recomp/gen/funcs.h").read_bytes()
    known = {int(x, 16) for x in re.findall(rb"#define FIDX_([0-9a-f]{8})", header)}
    dirty = set()
    context = {}

    def write_hook(uc, access, address, size, value, _):
        dirty.update(range(address & ~4095, ((address + size - 1) & ~4095) + 1, 4096))

    def code_hook(uc, address, size, _):
        context["instructions"] += 1
        wrapper, stub, thunk = context["wrapper"], context["stub"], context["thunk"]
        permitted = (wrapper <= address < wrapper + 10 or address == stub
                     or thunk <= address < thunk + 26 or 0x00EF0000 <= address < 0x00F10000)
        if not permitted:
            context["stop_target"] = address
            uc.emu_stop()

    u.hook_add(UC_HOOK_MEM_WRITE, write_hook)
    u.hook_add(UC_HOOK_CODE, code_hook)
    cases = []
    skipped = dict(nonmatching_wrapper=0, nonmatching_stub=0, nonmatching_thunk=0)
    for slot in range(0x008A54E8, 0x008A6A10, 4):
        for page in dirty:
            for base, raw in regions:
                if base <= page < base + len(raw):
                    u.mem_write(page, raw[page-base:page-base+4096])
                    break
        dirty.clear()
        wrapper = struct.unpack("<I", u.mem_read(slot, 4))[0]
        try:
            prefix = bytes(u.mem_read(wrapper, 10))
        except UcError:
            skipped["nonmatching_wrapper"] += 1
            continue
        if prefix[0] != 0xB9 or prefix[5] != 0xE8:
            skipped["nonmatching_wrapper"] += 1
            continue
        stub = (wrapper + 10 + struct.unpack("<i", prefix[6:10])[0]) & 0xFFFFFFFF
        stub_raw = bytes(u.mem_read(stub, 6))
        if stub_raw[:2] != b"\xff\x25":
            skipped["nonmatching_stub"] += 1
            continue
        pointer = struct.unpack("<I", stub_raw[2:])[0]
        thunk = struct.unpack("<I", u.mem_read(pointer, 4))[0]
        raw = bytes(u.mem_read(thunk, 26))
        if not (raw[0] == raw[5] == raw[10] == 0x68 and raw[15] == 0x9C
                and raw[16:20] == bytes.fromhex("816c2404") and raw[24:] == b"\x9d\xc3"):
            skipped["nonmatching_thunk"] += 1
            continue
        context.clear()
        context.update(wrapper=wrapper, stub=stub, thunk=thunk, instructions=0)
        for reg, value in zip(regs, state["registers"]):
            u.reg_write(reg, value)
        u.reg_write(UC_X86_REG_ESI, slot)
        u.reg_write(UC_X86_REG_EFLAGS, state["eflags"])
        try:
            u.emu_start(wrapper, 0, count=3000)
        except UcError as error:
            context["error"] = str(error)
        target = context.get("stop_target")
        result = dict(slot=f"{slot:08x}", wrapper=f"{wrapper:08x}", stub=f"{stub:08x}",
                      thunk=f"{thunk:08x}", instructions=context["instructions"],
                      wrapper_prefix_matches_original=prefix == original[wrapper-image_base:wrapper-image_base+10],
                      stub_matches_original=stub_raw == original[stub-image_base:stub-image_base+6],
                      thunk_matches_original=raw == original[thunk-image_base:thunk-image_base+26],
                      source_state="captured CPU and memory; ESI set to this table slot; each case independent",
                      body_executed=False, error=context.get("error"))
        if target is not None:
            live = bytes(u.mem_read(target, 32))
            orig = original[target-image_base:target-image_base+32]
            result.update(computed_target=f"{target:08x}", target_translated=target in known,
                          current_prefix_hex=live.hex(), current_prefix_matches_original=live == orig,
                          standard_msvc_seh_prefix=(live[:2] == b"\x6a\xff" and live[2] == 0x68
                              and live[7:21] == bytes.fromhex("64a1000000005064892500000000")))
        else:
            result["stop"] = "instruction_budget_or_fault"
        cases.append(result)
    missing = [c for c in cases if c.get("computed_target") and not c["target_translated"]]
    recovery_image = T.Image(str(executable))
    for item in missing:
        target = int(item["computed_target"], 16)
        instructions = recovery_image.recover(target, known - {target}, limit=4096)
        item["recovered_instructions"] = len(instructions)
        if not instructions:
            item["individual_emission_succeeded"] = False
            continue
        function = T.Function(target, "initializer_batch", instructions[-1].addr - target + 1, instructions)
        function.measure(recovery_image)
        translator = T.Translator(recovery_image, known | {target}, SimpleNamespace(eager_flags=False))
        translator.all_insn_addrs = known | function.addrs
        try:
            translator.prepare(function)
            translator.translate(function)
            item["individual_emission_succeeded"] = not translator.unmodelled
            item["recognized_seh_sites"] = function.seh_sites
        except T.TranslateError as error:
            item["individual_emission_succeeded"] = False
            item["emission_error"] = str(error)
    report = dict(executable_sha256=sha, snapshot=str(directory / "halt.json"),
                  generated_header_sha256=hashlib.sha256(header).hexdigest(),
                  table_start="008a54e8", table_end="008a6a10", cases=cases, skipped=skipped,
                  missing_computed_targets=missing,
                  candidate_standard_constructors=[c for c in missing if c["standard_msvc_seh_prefix"] and c["current_prefix_matches_original"]],
                  replaced_instructions_or_imports=False,
                  limitation="Independent captured-state wrapper cases; does not reproduce preceding initializer effects or execute constructors. Stops on first transfer outside the matched wrapper/stub/thunk and known dispatcher region.")
    (ROOT / "build/initializer-dispatch-batch.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(dict(cases=len(cases), skipped=skipped, missing=missing), indent=2))


if __name__ == "__main__":
    main()
