"""Bounded original-byte reference for the witnessed startup constructor.

This verifies three counter paths in Unicorn, not a full native game run or
browser execution. No original code, import, branch or return is replaced.
"""
import hashlib
import json
from pathlib import Path
import struct
import tomllib

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
    UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_ESP, UC_X86_REG_EIP,
)

ROOT = Path(__file__).resolve().parent


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text())
    executable = ROOT / cfg["game"]["developer_exe"]
    sha = hashlib.sha256(executable.read_bytes()).hexdigest()
    assert sha == cfg["game"]["sha256"]
    pe = pefile.PE(str(executable))
    image = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    results = []
    for counter in (1, 2, 0):
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(base, (len(image) + 4095) & ~4095)
        u.mem_write(base, image)
        u.mem_map(0x0EFF0000, 0x10000)
        stack, obj, ret = 0x0EFFFEB0, 0x00A93370, 0x0046B2E8
        for register, value in (
            (UC_X86_REG_EAX, 0x0084B010), (UC_X86_REG_EBX, 0),
            (UC_X86_REG_ECX, obj), (UC_X86_REG_EDX, 0),
            (UC_X86_REG_ESI, obj), (UC_X86_REG_EDI, 0x008A6A10),
            (UC_X86_REG_ESP, stack),
        ):
            u.reg_write(register, value)
        u.mem_write(stack, struct.pack("<I", ret))
        for address in (0x01511930, 0x01511936):
            u.mem_write(address, struct.pack("<I", counter))
        u.mem_write(obj, b"\xA5" * (70 * 20 + 8))
        ptr = bytes(u.mem_read(0x0085AD9C, 4))
        u.emu_start(0x014DEEF0, ret, count=5000)
        assert u.reg_read(UC_X86_REG_EIP) == ret
        assert u.reg_read(UC_X86_REG_ESP) == stack + 4
        assert u.reg_read(UC_X86_REG_ESI) == obj
        assert u.reg_read(UC_X86_REG_EDI) == 0x008A6A10
        for index in range(70):
            row = bytes(u.mem_read(obj + index * 20, 20))
            assert row[:5] == b"\xff\xff\xff\xff\x01"
            assert row[5:8] == b"\xa5" * 3
            assert row[8:12] == ptr
            assert row[12:20] == b"\x00" * 8
        assert bytes(u.mem_read(obj + 70 * 20, 8)) == b"\xA5" * 8
        after = [struct.unpack("<I", u.mem_read(a, 4))[0]
                 for a in (0x01511930, 0x01511936)]
        expected = [0x261, 0x2EC] if counter == 1 else [(counter - 1) & 0xFFFFFFFF] * 2
        assert after == expected
        results.append(dict(initial_counters=counter, final_counters=after,
                            initialized_records=70, correct_return=True,
                            preserved_callee_registers=True, bounds_verified=True))
    report = dict(executable_sha256=sha, reference="Unicorn x86 original bytes",
                  target="014deef0", caller_registers_from_browser=True,
                  counter_states_synthetic=True, cases=results,
                  browser_execution_verified=False, playable_verified=False)
    (ROOT / "build/startup-014deef0-reference.json").write_text(json.dumps(report, indent=2))
    print("Original constructor: 3 counter paths, 70 records each, returns and bounds verified")


if __name__ == "__main__":
    main()
