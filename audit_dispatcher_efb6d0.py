"""Reproducible dispatcher research with pristine guest image initialization.

No synchronization globals, context tables or native checks are patched. CPU
probes document missing original initialization, not an inferred return contract.
"""
import collections
import hashlib
import json
from pathlib import Path
import sys

import capstone as C
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_INVALID
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS, UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor/recomp-kit/tools/recomp'))
import translate as T
SHA = 'cd885d84bcbdacddc27bdbd6676e376557f118f090e71e0db7c746e72c949064'


def insrecord(i):
    return dict(address=i.address, bytes=bytes(i.bytes).hex(), mnemonic=i.mnemonic, operands=i.op_str)


def main():
    binary = ROOT / 'prepared/gta_sa.exe'
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == SHA
    image = T.Image(str(binary))
    source = ROOT / 'analysis/curated-core-checksum-neutral/functions/00efb6d0.asm'
    listed = T.parse_listing(str(source))
    decoder = C.Cs(C.CS_ARCH_X86, C.CS_MODE_32)
    decoder.detail = True
    native = image.recover(0xefb6d0, set())
    exported_addresses = {i.addr for i in listed}
    native_addresses = {i.addr for i in native}
    report = dict(executable_sha256=SHA, original_bytes_modified=False,
        export_instruction_count=len(listed), recovered_instruction_count=len(native),
        native_boundaries_missing_from_export=sorted(native_addresses-exported_addresses),
        exported_boundaries_missing_from_native_cfg=sorted(exported_addresses-native_addresses),
        initialized_globals={hex(a): image.data[a-image.base:a-image.base+size].hex()
            for a, size in ((0x1391c54, 2), (0x13920e4, 40), (0x1394514, 16))},
        probes=[])
    report['original_context_slots'] = []
    for index in range(10):
        pointer = image.rd32(0x13920e4+index*4)
        report['original_context_slots'].append(dict(index=index, pointer=pointer,
            signature_at_plus_24=image.data[pointer+0x24-image.base:pointer+0x28-image.base].hex(),
            selector_byte_at_plus_28=image.data[pointer+0x28-image.base:pointer+0x29-image.base].hex()))
    for start in (0x150a060, 0x150a070, 0x150c270, 0x150c2b0):
        cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        cpu.mem_map(image.base, (image.size+4095)&~4095)
        cpu.mem_write(image.base, bytes(image.data))
        cpu.mem_map(0x3000000, 0x10000)
        cpu.reg_write(UC_X86_REG_ESP, 0x3008000)
        cpu.reg_write(UC_X86_REG_EFLAGS, 0x202)
        for index, reg in enumerate((UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)):
            cpu.reg_write(reg, 0x12345678+index*0x01020304)
        counts = collections.Counter()
        trace = collections.deque(maxlen=24)
        memory = collections.deque(maxlen=24)
        invalid = []
        hits = []
        addresses = []
        code_reads = []
        modified_execution = {}
        def code_hook(uc, address, size, data):
            counts[address] += 1
            addresses.append(address)
            actual = bytes(uc.mem_read(address, size))
            original = image.data[address-image.base:address-image.base+size]
            if actual != original:
                modified_execution[address] = dict(address=address,
                    original_bytes=original.hex(), executed_bytes=actual.hex())
            trace.append(address)
            if address in (0x150a062, 0x150c2c2, 0x150a07a, 0x150c27a):
                hits.append(address)
        def memory_hook(uc, access, address, size, value, data):
            memory.append(dict(access=access, instruction=uc.reg_read(UC_X86_REG_EIP),
                               address=address, size=size, value=value))
            if access == 16 and start <= address < start+32:
                code_reads.append(dict(instruction=uc.reg_read(UC_X86_REG_EIP), address=address,
                    size=size, bytes=bytes(uc.mem_read(address, size)).hex()))
        def invalid_hook(uc, access, address, size, value, data):
            invalid.append(dict(access=access, instruction=uc.reg_read(UC_X86_REG_EIP),
                                address=address, size=size))
            return False
        cpu.hook_add(UC_HOOK_CODE, code_hook)
        cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, memory_hook)
        cpu.hook_add(UC_HOOK_MEM_INVALID, invalid_hook)
        error = None
        try:
            cpu.emu_start(start, 0, count=5000)
        except UcError as exc:
            error = str(exc)
        decoded_trace = []
        for address in trace:
            ins = next(decoder.disasm(image.data[address-image.base:address-image.base+15], address, count=1), None)
            if ins:
                decoded_trace.append(insrecord(ins))
        transfers = []
        for previous, successor in zip(addresses, addresses[1:]):
            ins = next(decoder.disasm(image.data[previous-image.base:previous-image.base+15], previous, count=1), None)
            if ins and ins.mnemonic in ('jmp', 'call', 'ret') and (not ins.operands or ins.operands[0].type != C.CS_OP_IMM):
                transfers.append(dict(instruction=insrecord(ins), successor=successor))
        report['probes'].append(dict(start=start, maximum_instructions=5000,
            executed_instructions=sum(counts.values()), stop_eip=cpu.reg_read(UC_X86_REG_EIP),
            unicorn_error=error, invalid_memory=invalid, most_frequent_instructions=counts.most_common(8),
            final_instruction_trace=decoded_trace, final_memory_accesses=list(memory),
            reads_from_original_stub_bytes=code_reads, computed_native_transfers=transfers[:64],
            dynamically_modified_executed_bytes=list(modified_execution.values()),
            executed_dispatcher_region_boundaries_absent_from_export=sorted(
                a for a in counts if 0xefb6d0 <= a < 0xefd4ca and a not in exported_addresses),
            alias_or_return_word_execution_hits=hits,
            final_lock_byte=bytes(cpu.mem_read(0x1391c54, 1)).hex(),
            initialization_policy='Only original mapped image, private zeroed stack, seeded integer registers and EFLAGS; no global writes forced'))
    report['scope'] = ('Pristine original-image probes are not a run from the game entry point. '
        'Failures identify prerequisites, not invalid native game logic. No globals or checks '
        'are overridden. No return contract or alias unreachability follows from these runs.')
    report['observations'] = ('Original synchronization bytes are 01/01 and context pointer '
        'slots are populated in the mapped image. No initialization was forced to pass the '
        'guard. In the two probes whose stub DWORD starts with EB, instruction efb7ef '
        'reads those four bytes as data through the caller-provided pointer. They are '
        'not executed as CPU short branches in these probes. Dispatcher context setup '
        'contains subtraction of its original self-call base, and computed branches '
        'reach native helpers and normal game code. Synthetic caller register seeds '
        'then cause unmapped memory accesses; this does not establish a valid game '
        'invocation or complete dispatcher semantics. Initial CPUID results are Unicorn '
        'CPU behavior, not a native Windows reference. No alias is proven unreachable.')
    report['next_validation'] = ('Recover/translate actual indirect dispatcher helper '
        'targets rather than interpreting return-word bytes as x86 entries. Capture a '
        'valid caller register/stack state through the real game entry, compare translated '
        'dispatcher context reads/writes and destinations with original native execution, '
        'and preserve dynamically changed code. Samples alone cannot certify a no-return '
        'contract or justify suppressing strict failures for existing aliases.')
    output = ROOT / 'analysis/dispatcher-efb6d0-audit.json'
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(report=str(output), probes=[dict(start=hex(p['start']),
        stop=hex(p['stop_eip']), error=p['unicorn_error'], steps=p['executed_instructions'])
        for p in report['probes']])))


if __name__ == '__main__':
    main()
