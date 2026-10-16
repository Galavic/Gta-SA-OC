"""Seed sweep over dispatcher stubs: enumerate indirect targets in bulk.

Pristine image, zeroed stack, varied synthetic register seeds. Synthetic
states prove candidacy, never validity: only the boot probe proves need.
Read-only except writing analysis/dispatcher-seed-sweep.json.
"""
import collections
import hashlib
import itertools
import json
from pathlib import Path
import sys

import capstone as C
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS,
                               UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
                               UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI,
                               UC_X86_REG_EBP)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor/recomp-kit/tools/recomp'))
import translate as T

SHA = 'cd885d84bcbdacddc27bdbd6676e376557f118f090e71e0db7c746e72c949064'
STARTS = (0x150a060, 0x150a070, 0x150c270, 0x150c2b0)
REGS = (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
        UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)
# helper band observed so far; collect wider then filter
LO, HI = 0x00e80000, 0x00f40000


def insrecord(i):
    return dict(address=i.address, bytes=bytes(i.bytes).hex(),
                mnemonic=i.mnemonic, operands=i.op_str)


def main():
    binary = ROOT / 'prepared/gta_sa.exe'
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == SHA
    image = T.Image(str(binary))
    decoder = C.Cs(C.CS_ARCH_X86, C.CS_MODE_32)
    decoder.detail = True
    # existing entries (listings + known helpers) to exclude from candidates
    owners = set()
    for tree in ('analysis/curated-core-q10-dispatcher/functions',):
        for path in (ROOT / tree).glob('*.asm'):
            for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
                m = __import__('re').match(r'^([0-9a-fA-F]{8})\s', line)
                if m:
                    owners.add(int(m.group(1), 16))
    data = [tuple(r) for r in json.loads((ROOT / 'analysis/curated-core-q10-dispatcher/inline-data.json').read_text())]
    image.declare_data_regions([(0x01348484, 0x01375484)] + data)

    def is_data(va):
        return any(lo <= va < hi for lo, hi in data)

    found = collections.Counter()
    witnesses = {}
    seeds = 0
    # Vary one register at a time over interesting values + a few combos.
    # Base seed matches the original audit; variations explore neighbors.
    values = (0x0, 0x1, 0x7, 0x40, 0x100, 0x1000, 0x12345678, 0x13920e4,
              0xdeadbeef, 0xffffffff)
    plans = []
    for start in STARTS:
        plans.append((start, None))
        for reg in REGS:
            for val in values:
                plans.append((start, (reg, val)))
    for start, override in plans:
        cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        cpu.mem_map(image.base, (image.size + 4095) & ~4095)
        cpu.mem_write(image.base, bytes(image.data))
        cpu.mem_map(0x3000000, 0x10000)
        cpu.reg_write(UC_X86_REG_ESP, 0x3008000)
        cpu.reg_write(UC_X86_REG_EFLAGS, 0x202)
        for index, reg in enumerate(REGS):
            cpu.reg_write(reg, 0x12345678 + index * 0x01020304)
        if override is not None:
            cpu.reg_write(override[0], override[1])
        addrs = []
        def hook(uc, address, size, data):
            addrs.append(address)
        cpu.hook_add(UC_HOOK_CODE, hook)
        seeds += 1
        try:
            cpu.emu_start(start, 0, count=5000)
        except UcError:
            pass
        for previous, successor in zip(addrs, addrs[1:]):
            if not (LO <= successor < HI):
                continue
            ins = next(decoder.disasm(image.data[previous - image.base:previous - image.base + 15],
                                      previous, count=1), None)
            if ins is None or ins.mnemonic not in ('jmp', 'call', 'ret'):
                continue
            if ins.operands and ins.operands[0].type == C.CS_OP_IMM:
                continue
            found[successor] += 1
            key = (previous, successor)
            if key not in witnesses:
                witnesses[key] = dict(instruction=insrecord(ins), successor=successor,
                                      seed_count=0)
            witnesses[key]['seed_count'] += 1
    cands = sorted(t for t in found if t not in owners and not is_data(t))
    report = dict(executable_sha256=SHA, original_bytes_modified=False,
                  starts=[hex(s) for s in STARTS], seed_runs=seeds,
                  scope=('Synthetic register seeds over pristine image; candidates only. '
                         'Need is proven by the boot probe, never by this sweep.'),
                  targets={f'{t:08x}': dict(hits=found[t],
                                            witnesses=[w for (p, s), w in witnesses.items() if s == t][:4])
                           for t in cands})
    out = ROOT / 'analysis/dispatcher-seed-sweep.json'
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(candidates=len(cands), seeds=seeds,
                          top=sorted(((f'{t:08x}', found[t]) for t in cands),
                                     key=lambda kv: -kv[1])[:30]), indent=2))


if __name__ == '__main__':
    main()
