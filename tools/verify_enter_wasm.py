"""Compare translated ENTER frame construction in real Wasm against x86.

Synthetic instruction tests only, not execution of GTA or its startup path.
"""
import itertools
import json
import os
from pathlib import Path
import struct
import subprocess

import verify_branch_wasm as B
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EFLAGS

ROOT, KIT, T = B.ROOT, B.KIT, B.T
STACK = B.STACK
START, LENGTH = STACK - 0x20000, 0x40000
FLAGS = B.FLAGS
FRAMES = (STACK, STACK - 0x80, STACK + 0x80, STACK + 0x10000, STACK + 0x10002)


def main():
    project = ROOT / "build/enter-wasm-project"
    output = ROOT / "build/enter-wasm"
    project.mkdir(parents=True, exist_ok=True)
    fixtures, translated = [], ['#include "x86.h"']
    for index, (prefix, allocation, nesting) in enumerate(itertools.product(
            (b"", b"\x67"),
            (0, 1, 0x20, 0xffff), (0, 1, 2, 7, 31, 32, 33, 255))):
        address = 0x00401000 + index * 0x100
        # Record the allocated ESP in EAX, then restore the caller's ESP
        # from ESI so RET remains valid without undoing ENTER's stack writes.
        code = prefix + b"\xc8" + struct.pack("<HB", allocation, nesting) + bytes.fromhex("89 e0 89 f4 c3")
        image = B.synthetic_image({address: code}, size=0x10000)
        instructions = image.recover(address, set(), bounds=(address, address + len(code)))
        function = T.Function(address, "enter_frame", len(code), instructions)
        function.measure(image)
        translator = T.Translator(image, {address}, B.Opts())
        translator.prepare(function)
        translated.append("\n".join(translator.translate(function)))
        fixtures.append((address, code))
    (project / "translated.c").write_text("\n".join(translated), encoding="utf-8")
    # Fail closed if an unexpected runtime transfer occurs in a fixture.
    harness = r'''#include "x86.h"
#include <stdio.h>
#include <stdlib.h>
uint8_t *g_mem;
uint32_t g_watch_base, g_watch_len;
RecompDirty g_dirty[RECOMP_DIRTY_SLOTS];
uint32_t g_dirty_count;
const int recomp_resumable_stacks = 0;
void recomp_watch_hit(uint32_t a, uint32_t n, uint64_t v) { abort(); }
void recomp_callback_return(X86 *c) { if (c->eip != GUEST_RETURN_SENTINEL) abort(); }
int recomp_is_call_return(uint32_t a) { abort(); return 0; }
int recomp_module_is_call_return(uint32_t a) { abort(); return 0; }
int32_t recomp_index_of(uint32_t a) { abort(); return -1; }
int32_t recomp_module_lookup(uint32_t a) { abort(); return -1; }
void recomp_call(X86 *c, uint32_t a) { abort(); }
void recomp_unknown_call(X86 *c, uint32_t a) { abort(); }
void recomp_jump(X86 *c, uint32_t a) { abort(); }
void recomp_unmodelled(X86 *c, uint32_t a) { abort(); }
'''
    harness += "\n".join(f"void fn_{address:08x}(X86 *c);" for address, _ in fixtures)
    harness += "\nint main(void) { g_mem=calloc(1,0x01000000u); if(!g_mem) return 2;\n"
    harness += "uint32_t frames[]={" + ",".join(f"{x}u" for x in FRAMES) + "};\n"
    harness += "uint32_t flags[]={" + ",".join(f"{x}u" for x in FLAGS) + "};\n"
    harness += f"for(unsigned form=0;form<{len(fixtures)};++form) for(unsigned fi=0;fi<{len(FRAMES)};++fi) for(unsigned fl=0;fl<{len(FLAGS)};++fl) {{\n"
    harness += f"for(unsigned j=0;j<{LENGTH}u;++j) g_mem[{START}u+j]=(uint8_t)(j*37u+11u);\n"
    harness += "X86 c={0}; for(unsigned j=0;j<8;++j) c.r[j]=0x11223300u+j;\n"
    harness += f"c.r[4]={STACK}u; c.r[5]=frames[fi]; c.r[6]={STACK}u; x86_set_eflags(&c,flags[fl]); wr32(c.r[4],GUEST_RETURN_SENTINEL);\n"
    harness += "switch(form) {" + "\n".join(f"case {i}:fn_{address:08x}(&c);break;" for i, (address, _) in enumerate(fixtures)) + "}\n"
    harness += 'for(unsigned j=0;j<8;++j) printf("%08x ",c.r[j]); printf("%08x %08x ",x86_get_eflags(&c),c.eip);\n'
    # Every location ENTER could write (maximum 32 dwords below initial ESP).
    harness += f'for(unsigned j=0;j<128;++j) printf("%02x",g_mem[{STACK-128}u+j]); printf("\\n");\n'
    harness += "} free(g_mem); return 0; }\n"
    (project / "oracle.c").write_text(harness, encoding="utf-8")
    (project / "CMakeLists.txt").write_text(f'''cmake_minimum_required(VERSION 3.24)
project(EnterWasmOracle C)
set(CMAKE_C_STANDARD 11)
add_executable(enter_oracle translated.c oracle.c)
target_include_directories(enter_oracle PRIVATE "{(KIT / 'runtime').as_posix()}")
target_compile_options(enter_oracle PRIVATE -O2)
target_link_options(enter_oracle PRIVATE "-sENVIRONMENT=node" "-sEXIT_RUNTIME=1" "-sALLOW_MEMORY_GROWTH=1")
''', encoding="utf-8")
    sdk = Path.home() / "GTASAWebToolchains/emsdk"
    os.environ["EMSDK"] = str(sdk)
    os.environ["EM_CONFIG"] = str(sdk / ".emscripten")
    os.environ["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + str(sdk / "upstream/emscripten") + os.pathsep + os.environ.get("PATH", "")
    subprocess.run([B.driver.cmake_tool("cmake"), "-S", str(project), "-B", str(output), "-G", "Ninja",
                    "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_TOOLCHAIN_FILE=" + (sdk / "upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake").as_posix()], check=True)
    B.driver.build("web", ["enter_oracle"], 2, build_dir=output)
    node = next((sdk / "node").glob("*/node.exe"))
    result = subprocess.run([str(node), str(output / "enter_oracle.js")], capture_output=True, text=True, check=True)
    actual = result.stdout.splitlines()
    emulator = Uc(UC_ARCH_X86, UC_MODE_32)
    emulator.mem_map(0x00400000, 0x100000)
    emulator.mem_map(START, LENGTH)
    emulator.mem_map(B.STOP & ~0xfff, 0x1000)
    initial = bytes((j * 37 + 11) & 255 for j in range(LENGTH))
    run = 0
    for address, code in fixtures:
        emulator.mem_write(address, code)
        for frame in FRAMES:
            for flags in FLAGS:
                emulator.mem_write(START, initial)
                registers = [0x11223300 + i for i in range(8)]
                registers[4], registers[5], registers[6] = STACK, frame, STACK
                for register, value in zip(B.REGISTERS, registers):
                    emulator.reg_write(register, value)
                emulator.reg_write(UC_X86_REG_EFLAGS, flags)
                emulator.mem_write(STACK, struct.pack("<I", B.STOP))
                emulator.emu_start(address, B.STOP, count=100)
                if emulator.reg_read(B.UC_X86_REG_EIP) != B.STOP:
                    raise AssertionError("Original x86 fixture did not return")
                expected = [emulator.reg_read(reg) & 0xffffffff for reg in B.REGISTERS]
                expected += [emulator.reg_read(UC_X86_REG_EFLAGS) & 0xffffffff, B.STOP]
                fields = actual[run].split()
                values = [int(x, 16) for x in fields[:10]]
                if values != expected:
                    raise AssertionError(f"Registers/flags/PC differ for {code.hex()}, frame={frame:x}, flags={flags:x}: {values} != {expected}")
                memory = bytes(emulator.mem_read(STACK - 128, 128)).hex()
                if fields[10] != memory:
                    raise AssertionError(f"Frame stack writes differ for {code.hex()}, frame={frame:x}, flags={flags:x}")
                run += 1
    if run != len(actual):
        raise AssertionError("Unexpected number of Wasm results")
    report = dict(wasm_runs=run, instruction_forms=len(fixtures),
                  registers_flags_pc_stack_identical=True,
                  scope="Synthetic nonfaulting 32-bit ENTER instructions in a flat 32-bit stack segment; 16-bit operands unsupported",
                  game_execution_verified=False)
    (ROOT / "build/enter-wasm-status.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
