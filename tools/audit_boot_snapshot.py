"""Continue exact dumped guest CPU state using original current instructions.

No import, allocation, instruction, branch, or return is substituted. Stops at
the first external instruction target, hardware fault, or instruction budget.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

import capstone
from unicorn import (
    Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE,
    UC_HOOK_MEM_INVALID, UC_HOOK_INTR, UC_MEM_FETCH_UNMAPPED, UC_MEM_FETCH_PROT,
)
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EBX,
    UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI,
    UC_X86_REG_EFLAGS, UC_X86_REG_EIP, UC_X86_REG_GDTR, UC_X86_REG_FS,
    UC_X86_REG_FS_BASE,
    UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS,
)

ROOT = Path(__file__).resolve().parents[1]


def descriptor(base, limit=0xFFFFF, access=0x93, flags=0xC):
    return struct.pack("<Q", (limit & 0xFFFF) | ((base & 0xFFFFFF) << 16)
                       | (access << 40) | (((limit >> 16) & 0xF) << 48)
                       | (flags << 52) | (((base >> 24) & 0xFF) << 56))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "build/boot-probe-current/halt.json")
    parser.add_argument("--budget", type=int, default=50000)
    args = parser.parse_args()
    metadata = json.loads(args.snapshot.read_text())
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    region_hashes = []
    intervals = []
    stem = args.snapshot.with_suffix("")
    for region in metadata["regions"]:
        assert region["written"]
        path = Path(str(stem) + region["suffix"])
        raw = path.read_bytes()
        assert len(raw) == region["size"]
        base = region["base"]
        u.mem_map(base, (len(raw) + 4095) & ~4095)
        u.mem_write(base, raw)
        intervals.append((base, base + len(raw)))
        region_hashes.append(dict(suffix=region["suffix"], sha256=hashlib.sha256(raw).hexdigest()))
    # A private GDT gives Unicorn's 32-bit segment translation the dumped TEB.
    # Its bytes are emulator metadata, not inserted guest executable code.
    gdt = 0x20000000
    assert not any(lo <= gdt < hi for lo, hi in intervals)
    u.mem_map(gdt, 4096)
    u.mem_write(gdt, b"\0" * 8 + descriptor(0, access=0x9B)
                + descriptor(0) + descriptor(metadata["fs_base"]))
    u.reg_write(UC_X86_REG_GDTR, (0, gdt, 31, 0))
    u.reg_write(UC_X86_REG_CS, 0x08)
    for segment in (UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS):
        u.reg_write(segment, 0x10)
    u.reg_write(UC_X86_REG_FS, 0x18)
    assert u.reg_read(UC_X86_REG_FS_BASE) == metadata["fs_base"]
    registers = (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EBX,
                 UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI)
    for register, value in zip(registers, metadata["registers"]):
        u.reg_write(register, value)
    u.reg_write(UC_X86_REG_EFLAGS, metadata["eflags"])
    header_raw = (ROOT / "build/recomp/gen/funcs.h").read_bytes()
    known = {int(a, 16) for a in re.findall(rb"#define FIDX_([0-9a-f]{8})", header_raw)}
    table = (ROOT / "build/recomp/gen/table.c").read_text()
    call_returns = {int(a, 16) for a in re.findall(r"0x([0-9a-f]{8})u", table.split("recomp_call_returns[] = {", 1)[1].split("};", 1)[0])}
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    transfers, missing, stop = [], [], {}
    previous = None
    count = 0
    floating_point_instructions = []
    tail = []

    def record_transfer(source, target):
        record = dict(source=f"{source.address:08x}", mnemonic=source.mnemonic,
                      operands=source.op_str, target=f"{target:08x}",
                      target_translated=target in known, target_is_call_return=target in call_returns)
        transfers.append(record)
        if target not in known:
            item = dict(record)
            if any(lo <= target and target + 32 <= hi for lo, hi in intervals):
                item["current_prefix_hex"] = bytes(u.mem_read(target, 32)).hex()
            missing.append(item)

    def code_hook(uc, address, size, _):
        nonlocal previous, count
        if previous is not None:
            if (previous.group(capstone.CS_GRP_CALL) or previous.group(capstone.CS_GRP_RET)
                    or previous.group(capstone.CS_GRP_IRET)
                    or (previous.group(capstone.CS_GRP_JUMP)
                        and address != previous.address + previous.size)):
                record_transfer(previous, address)
        count += 1
        tail.append(f"{address:08x}")
        del tail[:-20]
        if not any(lo <= address < hi for lo, hi in intervals):
            stop.update(reason="external_instruction_target", address=f"{address:08x}")
            uc.emu_stop()
            return
        instructions = list(decoder.disasm(bytes(uc.mem_read(address, size)), address, count=1))
        previous = instructions[0] if instructions else None
        if previous is not None and previous.mnemonic.startswith("f"):
            floating_point_instructions.append(dict(address=f"{address:08x}", mnemonic=previous.mnemonic))
        if count >= args.budget:
            stop.update(reason="instruction_budget", address=f"{address:08x}")
            uc.emu_stop()

    def fault_hook(uc, access, address, size, value, _):
        if previous is not None and access in (UC_MEM_FETCH_UNMAPPED, UC_MEM_FETCH_PROT):
            record_transfer(previous, address)
        stop.update(reason="unmapped_or_protected_memory", access=access,
                    address=f"{address:08x}", size=size, value=value)
        return False

    def interrupt_hook(uc, number, _):
        stop.update(reason="hardware_interrupt", number=number,
                    address=f"{uc.reg_read(UC_X86_REG_EIP):08x}")
        uc.emu_stop()

    u.hook_add(UC_HOOK_CODE, code_hook)
    u.hook_add(UC_HOOK_MEM_INVALID, fault_hook)
    u.hook_add(UC_HOOK_INTR, interrupt_hook)
    try:
        u.emu_start(metadata["target"], 0, count=args.budget + 1)
    except UcError as error:
        stop["unicorn_error"] = str(error)
    stop.setdefault("reason", "emulation_stopped")
    # A taken direct branch can stay inside its compiled body without needing
    # a dispatch-table alias. Do not turn such local labels into extra seeds.
    for transfer in missing:
        transfer["target_external_to_snapshot"] = not any(
            lo <= int(transfer["target"], 16) < hi for lo, hi in intervals)
        transfer["already_compiled_local_branch"] = False
        if transfer["mnemonic"].startswith("j") and transfer["operands"].startswith("0x"):
            label = "L_" + transfer["target"] + ": ;"
            source_comment = "/* " + transfer["source"] + " "
            for chunk in sorted((ROOT / "build/recomp/gen").glob("chunk_*.c")):
                text = chunk.read_text()
                target_position = text.find(label)
                source_position = text.find(source_comment)
                if target_position < 0 or source_position < 0:
                    continue
                definitions = list(re.finditer(r"(?:static )?void (?:body|fn)_([0-9a-f]{8})\(", text))
                owner_source = [m.group(1) for m in definitions if m.start() < source_position][-1]
                owner_target = [m.group(1) for m in definitions if m.start() < target_position][-1]
                if owner_source == owner_target:
                    transfer["already_compiled_local_branch"] = True
                    transfer["compiled_body"] = owner_source
                    transfer["compiled_chunk"] = chunk.name
                    break
    report = dict(snapshot=str(args.snapshot), executable_sha256=metadata["exe_sha256"],
                  snapshot_region_hashes=region_hashes,
                  generated_header_sha256=hashlib.sha256(header_raw).hexdigest(),
                  initial_state=metadata, fpu_snapshot_available=False,
                  floating_point_instructions=floating_point_instructions,
                  instructions=count, stop=stop, final_eip=f"{u.reg_read(UC_X86_REG_EIP):08x}",
                  final_registers=[u.reg_read(r) for r in registers], trace_tail=tail,
                  transfers=transfers, transfers_without_main_dispatch_entries=missing,
                  candidate_missing_guest_dispatch_entries=[item for item in missing
                      if not item["already_compiled_local_branch"] and not item["target_external_to_snapshot"]],
                  substituted_calls_or_instructions=False,
                  limitation="Exact dumped integer registers/EFLAGS/FS and memory; FPU state was not dumped. This bounded emulator continuation is not a Wasm/browser execution proof.")
    out = ROOT / "build/startup-snapshot-continuation.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(dict(instructions=count, stop=stop, missing_transfers=missing), indent=2))


if __name__ == "__main__":
    main()
