"""Exercise the pinned executable's Idle prefix in Unicorn, without rendering.

This verifies the busy-wait change and real elapsed timer input, not browser FPS.
No executable bytes are changed on disk or included in the report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile
import unicorn
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP

from configure_idle_pacing import IMAGE_SHA, ROOT, LIMIT_SITE

START, UPDATE = 0x0053E920, 0x0053E968
TIMER, DIVIDER, LAST_TICK = 0x00561A80, 0x00561A40, 0x00B72CA8


def run_prefix(code, patched, work_ms, frames=30):
    cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    cpu.mem_map(0x00400000, 0x00800000)
    cpu.mem_map(0x02000000, 0x10000)
    program = bytearray(code)
    if patched:
        program[0x2C] = 0  # The config replaces CMP EAX,14 with CMP EAX,0.
    cpu.mem_write(START, bytes(program))
    cpu.mem_write(TIMER, b"\xc3")
    cpu.mem_write(DIVIDER, b"\xc3")
    state = dict(now=0.0, epoch=0.0, reads=0, updates=0, elapsed=[])

    def on_code(uc, address, size, data):
        if address == TIMER:
            state["reads"] += 1
            # A deterministic real clock: one tick = one ms, with read cost.
            state["now"] += 0.125
            uc.reg_write(UC_X86_REG_EAX, int(state["now"] - state["epoch"]))
        elif address == DIVIDER:
            uc.reg_write(UC_X86_REG_EAX, 1)
        elif address == UPDATE:
            # The real CTimer::Update receives elapsed real time and rebases
            # the epoch used by GetCurrentTimeInCycles. It is not accelerated.
            state["elapsed"].append(state["now"] - state["epoch"])
            state["epoch"] = state["now"]
            state["updates"] += 1
            uc.emu_stop()

    cpu.hook_add(unicorn.UC_HOOK_CODE, on_code)
    waits = []
    for _ in range(frames):
        state["now"] += work_ms
        before = state["now"]
        cpu.reg_write(UC_X86_REG_ESP, 0x0200F000)
        cpu.emu_start(START, UPDATE + 5, count=1_000_000)
        waits.append(state["now"] - before)
    assert state["updates"] == frames, "Every frame must reach the original timer update"
    assert sum(state["elapsed"]) == state["now"], "Timer input must equal real elapsed time"
    return dict(work_ms=work_ms, frames=frames, timer_reads=state["reads"],
                prefix_elapsed_ms=waits, real_elapsed_ms=state["now"],
                timer_elapsed_ms=sum(state["elapsed"]),
                last_tick=struct.unpack("<I", cpu.mem_read(LAST_TICK, 4))[0])


def audit(image):
    raw = image.read_bytes()
    if hashlib.sha256(raw).hexdigest() != IMAGE_SHA:
        raise ValueError("Requires pinned executable")
    pe = pefile.PE(data=raw, fast_load=True)
    code = pe.get_data(START - pe.OPTIONAL_HEADER.ImageBase, UPDATE + 5 - START)
    assert code[0x2A:0x2F] == bytes.fromhex("83 f8 0e 72 e1")
    cases = []
    for cost in [5, 10, 20, 27, 40]:
        baseline = run_prefix(code, False, cost)
        candidate = run_prefix(code, True, cost)
        assert candidate["timer_reads"] == 3 * candidate["frames"]
        assert all(v == 0.375 for v in candidate["prefix_elapsed_ms"])
        assert any(v > 10 for v in baseline["prefix_elapsed_ms"])
        cases.append(dict(original=baseline, candidate=candidate))
    initial = pe.get_data(LIMIT_SITE - pe.OPTIONAL_HEADER.ImageBase, 10)
    assert initial == bytes.fromhex("c7 05 4c 70 c1 00 1e 00 00 00")
    gate = pe.get_data(0x00748D81 - pe.OPTIONAL_HEADER.ImageBase, 0x17)
    limiter_cases = []
    for fps in (30, 60):
        for elapsed in (10, 20, 40):
            cpu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
            cpu.mem_map(0x00400000, 0x00A00000)
            cpu.mem_map(0x02000000, 0x10000)
            instruction = initial[:6] + struct.pack("<I", fps)
            cpu.mem_write(LIMIT_SITE, instruction)
            cpu.emu_start(LIMIT_SITE, LIMIT_SITE + 10)
            assert struct.unpack("<I", cpu.mem_read(0x00C1704C, 4))[0] == fps
            cpu.mem_write(0x00748D81, gate)
            cpu.mem_write(0x00858C4C, struct.pack("<f", 1000.0))
            cpu.mem_write(0x0200F014, struct.pack("<f", elapsed))
            cpu.reg_write(UC_X86_REG_ESP, 0x0200F000)
            outcome = []
            def on_gate(uc, address, size, data):
                if address in (0x00748D98, 0x00748DA3):
                    outcome.append(address == 0x00748D98)
                    uc.emu_stop()
            cpu.hook_add(unicorn.UC_HOOK_CODE, on_gate)
            cpu.emu_start(0x00748D81, 0x00748DA4, count=50)
            assert outcome == [elapsed > 1000.0 / fps]
            limiter_cases.append(dict(limit_fps=fps, elapsed_ms=elapsed, enters_idle=outcome[0]))
    return dict(executable_sha256=IMAGE_SHA, cases=cases, limiter_cases=limiter_cases,
                browser_gameplay_verified=False, fps_gain_verified=False,
                scope="Actual x86 Idle prefix with deterministic timer callees; no GPU or game world")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=ROOT / "variants/singleplayer/prepared/gta_sa.exe")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.image)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Five Idle-prefix comparisons and six frame-limit gate checks passed; browser FPS unverified")
