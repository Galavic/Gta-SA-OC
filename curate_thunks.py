"""Split indirect jump thunks from misaligned, merged Ghidra body fragments.

Keep the raw Ghidra export. New bodies start at the exact stored target,
and their instructions are decoded from the verified original bytes.
"""
import hashlib
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import tomllib

import capstone
import pefile
import audit_core_data

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="analysis/curated-core")
    args = parser.parse_args()
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    binary = ROOT / cfg["game"]["developer_exe"]
    raw = binary.read_bytes()
    if hashlib.sha256(raw).hexdigest() != cfg["game"]["sha256"]:
        raise ValueError("Original executable checksum differs")
    pe = pefile.PE(data=raw)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    imports = {i.address for d in pe.DIRECTORY_ENTRY_IMPORT for i in d.imports}
    export = ROOT / "analysis/gta_sa.exe"
    core_data = audit_core_data.verify(binary, cfg["game"]["sha256"], export)
    out = ROOT / args.output
    shutil.copytree(export, out, dirs_exist_ok=True)
    index = (export / "functions.tsv").read_text(encoding="utf-8").splitlines()
    known = {int(line.split("\t")[0], 16) for line in index[1:]}
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    runtime_image = T.Image(str(binary))
    changes, refused, added = [], [], []
    sizes, call_sites, inline_data = {}, set(), set()
    inline_data.add(tuple(core_data["region"]))
    candidates, dispatched_functions = [], {}
    for function in sorted(known):
        lines = (export / "functions" / f"{function:08x}.asm").read_text(encoding="utf-8").splitlines()
        for line in lines:
            match = re.fullmatch(r"([0-9a-fA-F]+)\s+JMP dword ptr \[0x([0-9a-fA-F]+)\]", line)
            if match:
                candidates.append((function, int(match.group(1), 16), int(match.group(2), 16), lines))
    for function, address, slot, lines in candidates:
        listing = out / "functions" / f"{function:08x}.asm"
        if slot in imports or not base <= slot <= base + len(image) - 4:
            continue
        code = image[address - base:address - base + 6]
        if code != b"\xff\x25" + slot.to_bytes(4, "little"):
            raise ValueError("Thunk listing does not match original bytes")
        target = int.from_bytes(image[slot - base:slot - base + 4], "little")
        section = next((s for s in pe.sections if base + s.VirtualAddress <= target < base + s.VirtualAddress + s.Misc_VirtualSize), None)
        if section is None or not section.Characteristics & 0x20000000:
            continue
        if any(lo <= target < hi for lo, hi in cfg["translate"].get("data_regions", [])):
            continue
        decoded = []
        for ins in decoder.disasm(image[target - base:target - base + 128], target):
            decoded.append(ins)
            if ins.mnemonic in ("ret", "jmp"):
                break
        # CALL form passes its return-word address as the dispatcher metadata
        # argument too. Original bounded traces are retained separately. The
        # bytes after CALL belong to that metadata, not native fallthrough.
        shape = [i.mnemonic for i in decoded]
        call_form = (len(decoded) >= 2 and shape[:2] == ["push", "call"]
                     and decoded[0].size == 5 and decoded[1].size == 5
                     and decoded[0].op_str == hex(target + 10)
                     and decoded[1].op_str == "0xefb6d0")
        stack_form = (shape == ["push", "push", "push", "pushfd", "sub", "popfd", "ret"]
                      and decoded[4].op_str.split(",")[0] == "dword ptr [esp + 4]"
                      and decoded[0].op_str == hex(decoded[-1].address + decoded[-1].size)
                      and all(i.operands[0].type == capstone.CS_OP_IMM for i in decoded[:3])
                      and decoded[4].operands[1].type == capstone.CS_OP_IMM
                      and (decoded[2].operands[0].imm - decoded[4].operands[1].imm) & 0xFFFFFFFF == 0x00EFB6D0)
        if not call_form and not stack_form:
            refused.append(dict(entry=hex(address), target=hex(target), shape=shape))
            continue
        kind = "call_metadata" if call_form else "constant_stack"
        if call_form:
            decoded = decoded[:2]
            call_sites.add(target + 5)
            inline_data.add((target + 10, target + 14))
        # Preserve the original entry JMP. Its stored pointer is still read
        # by the original instruction; no hook or instruction replacement.
        if address == function:
            listing.write_text(lines[0] + "\n", encoding="utf-8")
            sizes[address] = 6
        dispatched_functions.setdefault(function, []).append((target - 1, decoded[-1].address + decoded[-1].size))
        target_file = out / "functions" / f"{target:08x}.asm"
        canonical = [runtime_image.to_insn(i) for i in decoded]
        target_file.write_text("\n".join(f"{i.addr:08x}  {i.rep or ''} {i.mnem} {','.join(i.ops)}".replace("  ", " ").rstrip() for i in canonical) + "\n", encoding="utf-8")
        length = decoded[-1].address + decoded[-1].size - target
        sizes[target] = length
        if target not in known:
            added.append(f"{target:08x}\taudited_stack_thunk_{target:08x}\t{length}\tassembly\tdecoded at original stored pointer")
        known.add(target)
        changes.append(dict(entry=hex(function), jump_site=hex(address), pointer=hex(slot), target=hex(target), kind=kind, instructions=len(decoded)))
    # Split only fragments overlapping this function's verified wrappers,
    # including Ghidra's known one-byte-early decode. Preserve other cross-
    # section paths; being in .dev1 alone does not prove a fragment unrelated.
    removed_fragments = []
    for function in dispatched_functions:
        section = next(s for s in pe.sections if base + s.VirtualAddress <= function < base + s.VirtualAddress + s.Misc_VirtualSize)
        if section.Name.rstrip(b"\0") == b".dev1":
            continue
        listing = out / "functions" / f"{function:08x}.asm"
        lines = listing.read_text(encoding="utf-8").splitlines()
        kept, removed = [], []
        for line in lines:
            at = int(line.split()[0], 16)
            owner = next((s for s in pe.sections if base + s.VirtualAddress <= at < base + s.VirtualAddress + s.Misc_VirtualSize), None)
            if (owner is not None and owner.Name.rstrip(b"\0") == b".dev1"
                    and any(lo <= at < hi for lo, hi in dispatched_functions[function])):
                removed.append(hex(at))
            else:
                kept.append(line)
        if removed:
            listing.write_text("\n".join(kept) + "\n", encoding="utf-8")
            removed_fragments.append(dict(entry=hex(function), removed_addresses=removed))
    rows = [index[0]]
    # Three original core targets were omitted by the export. One has an
    # empty one-byte function row despite being a real directly called body;
    # two are original INT3 fallthroughs after CRT ExitProcess calls.
    core_repairs = []
    call_site, core_entry, core_end = 0x0047282A, 0x00407800, 0x00407814
    call_bytes = image[call_site - base:call_site - base + 5]
    if (call_bytes[0] != 0xE8
            or call_site + 5 + int.from_bytes(call_bytes[1:], "little", signed=True) != core_entry):
        raise ValueError("Original core CALL no longer names the audited empty export")
    if (export / "functions" / f"{core_entry:08x}.asm").read_text(encoding="utf-8").strip():
        raise ValueError("Audited empty core export is no longer empty")
    core_instructions = runtime_image.recover(core_entry, set(), bounds=(core_entry, core_end))
    if [i.mnem for i in core_instructions] != ["MOV", "LEA", "MOV", "TEST", "SETNE", "RET"]:
        raise ValueError("Audited core body differs from its original instruction shape")
    canonical_text = "\n".join(f"{i.addr:08x}  {i.mnem} {','.join(i.ops)}".rstrip() for i in core_instructions) + "\n"
    (out / "functions" / f"{core_entry:08x}.asm").write_text(canonical_text, encoding="utf-8")
    sizes[core_entry] = core_end - core_entry
    core_repairs.append(dict(entry=hex(core_entry), reason="empty exported body", original_call=hex(call_site), instructions=len(core_instructions)))
    for caller, entry in ((0x008248E7, 0x008248ED), (0x0082B3BD, 0x0082B3C3)):
        if (image[caller - base:caller - base + 6] != b"\xff\x15\x0c\x92\x85\x00"
                or runtime_image.iat_names.get(0x0085920C) != "ExitProcess"
                or image[entry - base] != 0xCC or caller + 6 != entry):
            raise ValueError("Original CRT call/INT3 continuation differs")
        if entry in known:
            raise ValueError("Audited CRT continuation already has a function row")
        (out / "functions" / f"{entry:08x}.asm").write_text(f"{entry:08x}  INT3\n", encoding="utf-8")
        added.append(f"{entry:08x}\taudited_crt_int3_{entry:08x}\t1\tassembly\toriginal ExitProcess fallthrough instruction")
        known.add(entry)
        core_repairs.append(dict(entry=hex(entry), reason="original CRT INT3 continuation", original_call=hex(caller), instructions=1))
    for line in index[1:] + added:
        fields = line.split("\t")
        if int(fields[0], 16) in sizes:
            fields[2] = str(sizes[int(fields[0], 16)])
        rows.append("\t".join(fields))
    (out / "functions.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (out / "nonreturning-calls.json").write_text(json.dumps(sorted(call_sites)), encoding="utf-8")
    (out / "inline-data.json").write_text(json.dumps(sorted(inline_data)), encoding="utf-8")
    (out / "core-data-check.json").write_text(json.dumps(core_data, indent=2), encoding="utf-8")
    (out / "thunk-curation.json").write_text(json.dumps(dict(original_bytes_modified=False, raw_export_modified=False, changes=changes, refused=refused, split_fragments=removed_fragments, core_repairs=core_repairs, runtime_verified=False), indent=2), encoding="utf-8")
    print(f"Split {len(changes)} stored-target thunks; {len(call_sites)} CALL metadata contracts; {len(refused)} other shapes retained. Raw export and original executable unchanged.")


if __name__ == "__main__":
    main()
