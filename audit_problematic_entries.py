"""Audit two operand-overlapping exports without declaring them unreachable.

Only writes the named research report. Direct-edge evidence is decoded from
immutable original bytes; bounded CPU runs establish the surrounding paths,
not absence of alternate/computed execution.
"""
from pathlib import Path
import hashlib
import json
import re
import struct
import sys

import capstone as C
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor/recomp-kit/tools/recomp'))
import translate as T

SHA = 'cd885d84bcbdacddc27bdbd6676e376557f118f090e71e0db7c746e72c949064'
TARGETS = {0x150a062: (0x150a060, 0x150a065, 0xefb6d0),
           0x150c2c2: (0x150c2b0, 0x150c2ca, 0xf0c628-0x10f58)}
REGS = [UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]


def record(ins):
    return dict(address=ins.address, bytes=bytes(ins.bytes).hex(),
                mnemonic=ins.mnemonic, operands=ins.op_str)


def main():
    binary = ROOT / 'prepared/gta_sa.exe'
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == SHA
    image = T.Image(str(binary))
    decoder = C.Cs(C.CS_ARCH_X86, C.CS_MODE_32)
    decoder.detail = True
    source = ROOT / 'analysis/curated-core-checksum-neutral'
    boundaries = set()
    text_refs = {t: [] for t in TARGETS}
    exported = {t: [] for t in TARGETS}
    for listing in sorted((source / 'functions').glob('*.asm')):
        for line in listing.read_text(encoding='utf-8').splitlines():
            match = re.match(r'^([0-9a-fA-F]{8})\s+(.*)', line)
            if not match:
                continue
            addr = int(match[1], 16)
            boundaries.add(addr)
            for target in TARGETS:
                if re.search(r'(?<![0-9a-fA-F])(?:0x)?0*' + f'{target:x}' + r'(?![0-9a-fA-F])', match[2], re.I):
                    text_refs[target].append(dict(listing=listing.name, address=addr, line=line))
                if addr == target:
                    exported[target].append(dict(listing=listing.name, line=line))
    report = dict(executable_sha256=SHA, input=str(source.relative_to(ROOT)),
                  original_bytes_modified=False, input_modified=False,
                  listed_instruction_boundaries=len(boundaries), entries=[])
    for target, (start, end, stop) in TARGETS.items():
        surrounding = list(decoder.disasm(image.data[start-image.base:end-image.base], start))
        containing = next(i for i in surrounding if i.address < target < i.address+i.size)
        pointers = []
        needle = struct.pack('<I', target)
        pos = image.data.find(needle)
        while pos >= 0:
            pointers.append(image.base+pos)
            pos = image.data.find(needle, pos+1)
        # Scan every byte in executable mapped ranges. Raw hits are not called
        # actual branches unless they coincide with an exported boundary.
        edges = []
        for lo, hi, _ in image.exec_ranges:
            blob = image.data[lo-image.base:hi-image.base]
            for opcode in (0xe8, 0xe9, 0x0f, 0xea, 0x9a):
                offset = blob.find(bytes([opcode]))
                while offset >= 0:
                    addr = lo+offset
                    raw = blob[offset:offset+15]
                    candidate = False
                    if opcode in (0xe8, 0xe9) and len(raw) >= 5:
                        candidate = (addr+5+struct.unpack('<i', raw[1:5])[0]) & 0xffffffff == target
                    elif opcode == 0x0f and len(raw) >= 6 and 0x80 <= raw[1] <= 0x8f:
                        candidate = (addr+6+struct.unpack('<i', raw[2:6])[0]) & 0xffffffff == target
                    elif opcode in (0xea, 0x9a) and len(raw) >= 7:
                        candidate = struct.unpack('<I', raw[1:5])[0] == target
                    if candidate:
                        ins = next(decoder.disasm(raw, addr, count=1), None)
                        if ins:
                            edges.append(dict(**record(ins), exported_instruction_boundary=addr in boundaries))
                    offset = blob.find(bytes([opcode]), offset+1)
        for addr in range(target-130, target+127):
            offset = addr-image.base
            raw = image.data[offset:offset+15]
            if len(raw) >= 2 and (raw[0] == 0xeb or 0x70 <= raw[0] <= 0x7f or 0xe0 <= raw[0] <= 0xe3):
                if (addr+2+struct.unpack('<b', raw[1:2])[0]) & 0xffffffff == target:
                    ins = next(decoder.disasm(raw, addr, count=1), None)
                    if ins:
                        edges.append(dict(**record(ins), exported_instruction_boundary=addr in boundaries))
        for edge in edges:
            addr = edge['address']
            preceding = next(decoder.disasm(image.data[addr-5-image.base:addr-image.base], addr-5, count=1), None)
            if preceding and preceding.address+preceding.size == addr and preceding.mnemonic == 'call':
                edge['immediately_preceding_native_call'] = record(preceding)
                edge['is_original_return_word_of_call'] = True
                edge['caller_is_exported_instruction_boundary'] = preceding.address in boundaries
            edge['source_bytes_context'] = image.data[addr-10-image.base:addr+10-image.base].hex()
        runs = []
        for seed, flags in enumerate((0x202, 0x243, 0xa96)):
            cpu = Uc(UC_ARCH_X86, UC_MODE_32)
            cpu.mem_map(0, 0x4000000)
            cpu.mem_write(image.base, bytes(image.data))
            sp = 0x3008000
            values = [(0x12345678 + seed*0x11111111 + i*0x01020304) & 0xffffffff for i in range(7)]
            for reg, value in zip(REGS, values):
                cpu.reg_write(reg, value)
            cpu.reg_write(UC_X86_REG_ESP, sp)
            cpu.reg_write(UC_X86_REG_EFLAGS, flags)
            cpu.emu_start(start, stop, count=32)
            expected_sp = sp-8
            words = list(struct.unpack('<II', cpu.mem_read(expected_sp, 8)))
            # PUSHFD temporarily adds a top slot. SUB [ESP+4] adjusts the
            # third pushed word, which POPFD/RET then consume as the target.
            expected_words = ([0x150a06a, 0x150a06a] if target == 0x150a062
                              else [0x40619c, 0x150c2ca])
            assert cpu.reg_read(UC_X86_REG_EIP) == stop
            assert cpu.reg_read(UC_X86_REG_ESP) == expected_sp
            assert [cpu.reg_read(r) for r in REGS] == values
            assert cpu.reg_read(UC_X86_REG_EFLAGS) == flags
            assert words == expected_words
            runs.append(dict(seed=seed, eflags=flags, stop_eip=stop,
                             stack_delta=expected_sp-sp, retained_stack_words=words,
                             all_integer_registers_preserved=True))
        report['entries'].append(dict(address=target, exported_lines=exported[target],
            surrounding_native_instructions=[record(i) for i in surrounding],
            containing_native_instruction=record(containing),
            unaligned_pointer_occurrences=pointers, literal_text_references=text_refs[target],
            original_byte_direct_edge_candidates=edges,
            surrounding_path_unicorn_runs=runs,
            indirect_entry_absence_proven=False,
            deletion_or_data_quarantine_justified=False))
    report['conclusion'] = ('Both exports overlap operands of verified surrounding native paths. '
        'Short JMP bytes targeting each alias occur immediately after another original CALL '
        'to efb6d0. These are not listed instruction boundaries and may be dispatcher data; '
        'their meaning requires auditing that dispatcher, not suppressing them. '
        'No claim of unreachability follows from absent pointer/text references. Preserve the '
        'bytes and potential alternate execution; repair enclosing native entries separately. '
        'A strict port still requires validated handling of these alternate instructions '
        'or stronger original control-flow proof before retiring their dispatch entries.')
    report['direct_edge_scan_scope'] = ('Unprefixed relative32 E8/E9 and 0F80..8F, '
        'relative8 JMP/Jcc/LOOP-family, and immediate far32 EA/9A opcode candidates. '
        'Scans raw executable bytes, including possible operands/data. Does not prove '
        'absence of computed transfers, operand-size16/prefixed transfers, dynamically '
        'modified code, or virtual instruction decoding by efb6d0.')
    report['translator_evidence'] = dict(source='vendor/recomp-kit/tools/recomp/translate.py',
        listed_entry_strength=4, listed_entries_initially_protected=True,
        pointer_interior_filter_does_not_reject_already_exported_listings=True,
        basis='listed_functions/protected_entries/entry_strength initialization in main translation driver')
    dispatcher_addresses = (0xefb6d0, 0xefb6d1, 0xefb6d2, 0xefb6d7,
        0xefb750, 0xefb74c, 0xefb7e2, 0xefb7e6, 0xefb7ec, 0xefb7ef,
        0xefb7f4, 0xefb7f9, 0xefb800, 0xefb802, 0xefb807,
        0xefb83d, 0xefb843, 0xefb846)
    report['dispatcher_static_original_bytes'] = [record(next(decoder.disasm(
        image.data[a-image.base:a-image.base+15], a, count=1))) for a in dispatcher_addresses]
    report['dispatcher_observation_limits'] = ('The six Unicorn runs stop upon entering '
        'efb6d0 and do not execute the dispatcher. Static original-byte evidence shows '
        'PUSHAD/PUSHFD/CALL-to-next, lock-protected global state, reads from caller stack, '
        'a DWORD read through a caller-provided address, construction of a context-like '
        'structure, and computed JMP EDX. VM interpretation of the EB bytes is only a '
        'hypothesis; no dispatcher return contract or final destination has been proven.')
    output = ROOT / 'analysis/problematic-entry-audit.json'
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(entries=len(report['entries']), surrounding_native_runs=6,
                         report=str(output), quarantine_justified=False)))


if __name__ == '__main__':
    main()
