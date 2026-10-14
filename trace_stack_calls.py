"""Bounded diagnostic of original stack-call wrappers in private emulated RAM.

No installed executable is run or modified. A zeroed synthetic register state
does not establish startup, licensing, or game-execution compatibility.
"""
import json
from pathlib import Path
import sys

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def main():
    image = T.Image(str(ROOT / "original/gta_sa.exe"))
    results = []
    for target in (0x0150E4B0, 0x0150C850, 0x01509790, 0x01509610, 0x0150BB20):
        emulator = Uc(UC_ARCH_X86, UC_MODE_32)
        emulator.mem_map(image.base, (len(image.data) + 0xFFF) & ~0xFFF)
        emulator.mem_write(image.base, image.data)
        emulator.mem_map(0x0E000000, 0x10000)
        emulator.reg_write(UC_X86_REG_ESP, 0x0E008000)
        emulator.reg_write(UC_X86_REG_EFLAGS, 0x202)
        result = dict(wrapper=hex(target), executed_instructions=0, synthetic_context=True, runtime_verified=False)
        def observe(uc, address, size, user):
            result["executed_instructions"] += 1
            if address == target + 10:
                result["stop"] = "reached_inline_call_continuation"
                uc.emu_stop()
            elif address < 0x00CA0000:
                result["stop"] = "transferred_to_main_image_code"
                uc.emu_stop()
        emulator.hook_add(UC_HOOK_CODE, observe)
        try:
            emulator.emu_start(target, 0, count=100000)
            result.setdefault("stop", "instruction_budget")
        except UcError as error:
            result["stop"] = str(error)
        result["last_eip"] = hex(emulator.reg_read(UC_X86_REG_EIP))
        results.append(result)
    (ROOT / "analysis/stack-call-traces.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
