"""Execute translated branch fixtures in Wasm and compare them with original x86.

The small test host is only an instruction oracle; it is not a game runtime.
Compilation goes through the kit build driver. No original assets are changed.
"""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tomllib

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX,
    UC_X86_REG_EBX, UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_ESI,
    UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_EFLAGS, UC_X86_REG_GDTR,
    UC_X86_REG_CS, UC_X86_REG_SS)

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "vendor/recomp-kit"
sys.path.insert(0, str(KIT / "tools/recomp/tests"))
from test_translate_driver import synthetic_image
from test_translate_insns import Opts
import translate as T

spec = importlib.util.spec_from_file_location("kit_build", KIT / "tools/build.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)

FORMS = (("LOOP", b"\xe2"), ("LOOPE", b"\xe1"), ("LOOPNE", b"\xe0"),
         ("LOOPZ", b"\xe1"), ("LOOPNZ", b"\xe0"),
         ("JCXZ", b"\x67\xe3"), ("JECXZ", b"\xe3"),
         ("CX_LOOP", b"\x67\xe2"), ("CX_LOOPE", b"\x67\xe1"), ("CX_LOOPNE", b"\x67\xe0"))
COUNTERS = (0, 1, 2, 0x10000, 0x10001, 0xFFFFFFFF, 0xABCD0000, 0xABCD0001, 0xABCD0002)
FLAGS = (0x202, 0x243, 0xAD7)
SEGMENT_FORMS = (("SS_RELOAD32", bytes.fromhex("16 17 66 8c d0 c3")),
                 ("SS_RELOAD16", bytes.fromhex("66 16 66 17 66 8c d0 c3")),
                 ("SS_RELOAD_FROM_STACK", bytes.fromhex("68 23 00 00 00 17 66 8c d0 c3")),
                 ("SS_POP32", bytes.fromhex("17 66 8c d0 c3")))
ZERO_FORMS = (("ZERO_EAX", bytes.fromhex("31 c0 74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")),
              ("ZERO_AX", bytes.fromhex("66 31 c0 74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")),
              ("ZERO_AL", bytes.fromhex("30 c0 74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")),
              ("ZERO_AH", bytes.fromhex("30 e4 74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")),
              ("ZERO_NZ", bytes.fromhex("31 c0 75 06 b8 01 00 00 00 c3 0f 0b c3")),
              ("ZERO_FIXED_NULL", bytes.fromhex("31 c0 74 08 bc 00 00 00 00 90 ff e4 c3")),
              ("ZERO_UNKNOWN_JUMP", bytes.fromhex("31 c0 74 02 ff e2 c3")),
              ("INDEPENDENT_JE_ENTRY", bytes.fromhex("74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")),
              ("INDEPENDENT_JNE_ENTRY", bytes.fromhex("75 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")),
              ("INCOMING_CONDITIONAL", bytes.fromhex("75 02 31 c0 74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")),
              ("OVERLAPPING_ZERO", bytes.fromhex("50 9c 31 c0 74 01 e8 9d 58 c3 90 90 90 90")))
STACK, STOP = 0x00600000, 0x0FDFFF00
REGISTERS = (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EBX,
             UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EDI)


def main():
    project = ROOT / "build/branch-wasm-project"
    output = ROOT / "build/branch-wasm"
    project.mkdir(parents=True, exist_ok=True)
    fixtures, translated = [], ['#include "x86.h"']
    forms = [(name, opcode + b"\x06\xb8\x01\0\0\0\xc3\xb8\x02\0\0\0\xc3") for name, opcode in FORMS]
    forms += list(SEGMENT_FORMS)
    forms += list(ZERO_FORMS)
    for index, (name, code) in enumerate(forms):
        address = 0x00401000 + index * 0x100
        image = synthetic_image({address: code}, size=0x10000)
        instructions = image.recover(address, set())
        if name in ("ZERO_FIXED_NULL", "ZERO_UNKNOWN_JUMP"):
            # Preserve the original unreachable listing so the emission
            # proof, rather than recursive recovery alone, is exercised.
            image.md.detail = True
            instructions = [image.to_insn(ci) for ci in image.md.disasm(code, address)]
            image.md.detail = False
        if name in ("LOOPZ", "LOOPNZ"):
            instructions[0].mnem = name  # Ghidra aliases, same original bytes.
        taken = address + len(FORMS[index][1]) + 1 + 6 if index < len(FORMS) else None
        if taken is not None and taken not in {i.addr for i in instructions}:
            raise AssertionError("Recovery omitted the branch's original taken target")
        function = T.Function(address, name, len(code), instructions)
        function.measure(image)
        translator = T.Translator(image, {address}, Opts())
        translator.prepare(function)
        translated.append("\n".join(translator.translate(function)))
        if name.startswith("ZERO_") or name == "OVERLAPPING_ZERO":
            if not function.proven_zero_branches:
                raise AssertionError("The original-byte single-entry branch was not proven")
            if name == "OVERLAPPING_ZERO" and "CALL" in translated[-1]:
                raise AssertionError("Impossible overlapping CALL was retained")
        elif name.startswith("INDEPENDENT_") and function.proven_zero_branches:
            raise AssertionError("An independently entered conditional branch was folded")
        fixtures.append((address, name, code))
    # A real original GTA function, whose Ghidra export had an empty body.
    # Exercise its table read under bounded synthetic post-load guest states.
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    original = ROOT / cfg["game"]["developer_exe"]
    if hashlib.sha256(original.read_bytes()).hexdigest() != cfg["game"]["sha256"]:
        raise ValueError("Original GTA executable checksum differs")
    original_image = T.Image(str(original))
    address, end = 0x00407800, 0x00407814
    instructions = original_image.recover(address, set(), bounds=(address, end))
    function = T.Function(address, "original_core_table_read", end - address, instructions)
    function.measure(original_image)
    translator = T.Translator(original_image, {address}, Opts())
    translator.prepare(function)
    translated.append("\n".join(translator.translate(function)))
    fixtures.append((address, "ORIGINAL_GTA_CORE", original_image.data[address - original_image.base:end - original_image.base]))
    ss_index = next(i for i, (_, name, _) in enumerate(fixtures) if name == "SS_POP32")
    overlap_index = next(i for i, (_, name, _) in enumerate(fixtures) if name == "OVERLAPPING_ZERO")
    core_index = len(fixtures) - 1
    (project / "translated.c").write_text("\n".join(translated), encoding="utf-8")
    prototypes = "\n".join(f"void fn_{a:08x}(X86 *c);" for a, _, _ in fixtures)
    calls = "\n".join(f"case {i}: fn_{a:08x}(&c); break;" for i, (a, _, _) in enumerate(fixtures))
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
    harness += prototypes + "\nint main(int argc, char **argv) {\n"
    harness += "g_mem = calloc(1, 0x01000000u); if (!g_mem) return 2;\n"
    harness += "if(argc>1) { X86 c={0}; c.r[4]=0x00600000u; c.eflags_misc=argc>2 ? strtoul(argv[2],0,0) : 0x202u;\n"
    harness += f"wr32(c.r[4],strtoul(argv[1],0,0)); wr32(c.r[4]+4,GUEST_RETURN_SENTINEL); fn_{fixtures[ss_index][0]:08x}(&c); free(g_mem); return 0; }}\n"
    harness += "uint32_t counts[] = {" + ",".join(f"0x{x:x}u" for x in COUNTERS) + "};\n"
    harness += "uint32_t flags[] = {" + ",".join(f"0x{x:x}u" for x in FLAGS) + "};\n"
    harness += f"for(unsigned form=0; form<{len(fixtures)}; ++form)\n"
    harness += f"for(unsigned ci=0; ci<{len(COUNTERS)}; ++ci) for(unsigned fi=0; fi<{len(FLAGS)}; ++fi) {{\n"
    harness += "X86 c = {0}; for(unsigned j=0;j<8;++j) c.r[j] = 0x11223300u+j;\n"
    harness += "c.r[1]=counts[ci]; c.r[4]=0x00600000u; x86_set_eflags(&c,flags[fi]); wr32(c.r[4],GUEST_RETURN_SENTINEL);\n"
    harness += f"if(form=={ss_index}) {{ wr32(c.r[4],0x23); wr32(c.r[4]+4,GUEST_RETURN_SENTINEL); }}\n"
    harness += f"if(form=={core_index}) {{ uint32_t arg=counts[ci]%17u; wr32(c.r[4]+4,arg); wr32(0x008e734cu+20u*arg,fi==0 ? 0u : (fi==1 ? 0x11223344u : 0xffffffffu)); }}\n"
    harness += "switch(form) {" + calls + "}\n"
    harness += 'for(unsigned j=0;j<8;++j) printf("%08x ",c.r[j]); printf("%08x %08x",x86_get_eflags(&c),c.eip);\n'
    harness += f'if(form=={overlap_index}) printf(" %08x %08x",rd32(0x005ffff8u),rd32(0x005ffffcu)); printf("\\n");\n'
    harness += "} free(g_mem); return 0; }\n"
    (project / "oracle.c").write_text(harness, encoding="utf-8")
    cmake = f'''cmake_minimum_required(VERSION 3.24)
project(BranchWasmOracle C)
set(CMAKE_C_STANDARD 11)
add_executable(branch_oracle translated.c oracle.c)
target_include_directories(branch_oracle PRIVATE "{(KIT / 'runtime').as_posix()}")
target_compile_options(branch_oracle PRIVATE -O2)
target_link_options(branch_oracle PRIVATE "-sENVIRONMENT=node" "-sEXIT_RUNTIME=1" "-sALLOW_MEMORY_GROWTH=1")
'''
    (project / "CMakeLists.txt").write_text(cmake, encoding="utf-8")
    sdk = Path.home() / "GTASAWebToolchains/emsdk"
    os.environ["EMSDK"] = str(sdk)
    os.environ["EM_CONFIG"] = str(sdk / ".emscripten")
    os.environ["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + str(sdk / "upstream/emscripten") + os.pathsep + os.environ.get("PATH", "")
    subprocess.run([driver.cmake_tool("cmake"), "-S", str(project), "-B", str(output), "-G", "Ninja",
                    "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_TOOLCHAIN_FILE=" + (sdk / "upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake").as_posix()], check=True)
    driver.build("web", ["branch_oracle"], 2, build_dir=output)
    node = next((sdk / "node").glob("*/node.exe"))
    result = subprocess.run([str(node), str(output / "branch_oracle.js")], capture_output=True, text=True, check=True)
    actual = [[int(x, 16) for x in line.split()] for line in result.stdout.splitlines()]
    subprocess.run([str(node), str(output / "branch_oracle.js"), "0x23"], capture_output=True, check=True)
    rejected = 0
    for selector, flags in (("0x10", "0x202"), ("0x3b", "0x202"), ("0x23", "0x302")):
        guarded = subprocess.run([str(node), str(output / "branch_oracle.js"), selector, flags], capture_output=True)
        if guarded.returncode == 0:
            raise AssertionError("Segment descriptor change or single-step state was silently accepted")
        rejected += 1
    emulator = Uc(UC_ARCH_X86, UC_MODE_32)
    emulator.mem_map(0x00400000, 0x100000)
    emulator.mem_map(STACK - 0x1000, 0x20000)
    emulator.mem_map(STOP & ~0xFFF, 0x1000)
    emulator.mem_map(0x008E7000, 0x1000)
    # Enter CPL3 through a real protected-mode IRET. Directly writing CS's
    # selector alone does not update Unicorn's internal privilege level.
    emulator.mem_map(0x10000, 0x1000)
    descriptors = bytearray(64)
    for slot, descriptor in {1: 0x00CF9A000000FFFF, 2: 0x00CF92000000FFFF,
                             3: 0x00CFFA000000FFFF, 4: 0x00CFF2000000FFFF}.items():
        descriptors[slot * 8:slot * 8 + 8] = struct.pack("<Q", descriptor)
    emulator.mem_write(0x10000, bytes(descriptors))
    emulator.reg_write(UC_X86_REG_GDTR, (0, 0x10000, len(descriptors) - 1, 0))
    emulator.reg_write(UC_X86_REG_CS, 8)
    emulator.reg_write(UC_X86_REG_SS, 16)
    emulator.mem_write(0x00400F00, b"\xcf")
    emulator.mem_write(STACK + 0x700, struct.pack("<IIIII", fixtures[0][0], 0x1B, 0x202, STACK, 0x23))
    emulator.reg_write(UC_X86_REG_ESP, STACK + 0x700)
    emulator.emu_start(0x00400F00, fixtures[0][0], count=10)
    if emulator.reg_read(UC_X86_REG_CS) != 0x1B or emulator.reg_read(UC_X86_REG_SS) != 0x23:
        raise AssertionError("Original x86 fixtures did not enter the flat Win32 segment context")
    expected = []
    for address, name, code in fixtures:
        emulator.mem_write(address, code)
        for counter in COUNTERS:
            for flags in FLAGS:
                registers = [0x11223300 + i for i in range(8)]
                registers[1], registers[4] = counter, STACK
                for register, value in zip(REGISTERS, registers):
                    emulator.reg_write(register, value)
                emulator.reg_write(UC_X86_REG_EFLAGS, flags)
                emulator.mem_write(STACK, struct.pack("<I", STOP))
                if name == "SS_POP32":
                    emulator.mem_write(STACK, struct.pack("<II", 0x23, STOP))
                elif name == "ORIGINAL_GTA_CORE":
                    argument = counter % 17
                    emulator.mem_write(STACK + 4, struct.pack("<I", argument))
                    value = (0, 0x11223344, 0xFFFFFFFF)[FLAGS.index(flags)]
                    emulator.mem_write(0x008E734C + 20 * argument, struct.pack("<I", value))
                emulator.emu_start(address, STOP, count=100)
                if emulator.reg_read(UC_X86_REG_SS) != 0x23:
                    raise AssertionError("Original segment fixture changed the stack descriptor")
                expected.append([emulator.reg_read(r) for r in REGISTERS] + [emulator.reg_read(UC_X86_REG_EFLAGS), emulator.reg_read(UC_X86_REG_EIP)])
                if name == "OVERLAPPING_ZERO":
                    expected[-1].extend(struct.unpack("<II", bytes(emulator.mem_read(STACK - 8, 8))))
    if actual != expected:
        # TEST/XOR leave AF undefined. The overlapping fixture restores
        # saved flags with POPFD, so its AF remains defined and is compared.
        for form, (_, name, _) in enumerate(fixtures):
            if name not in ("ORIGINAL_GTA_CORE", "INCOMING_CONDITIONAL") and not name.startswith("ZERO_"):
                continue
            start = form * len(COUNTERS) * len(FLAGS)
            for index in range(start, start + len(COUNTERS) * len(FLAGS)):
                if name == "INCOMING_CONDITIONAL" and not (FLAGS[index % len(FLAGS)] & 0x40):
                    continue  # This path bypasses XOR and must preserve AF.
                if index < len(actual):
                    actual[index][8] &= ~0x10
                expected[index][8] &= ~0x10
    if actual != expected:
        if len(actual) != len(expected):
            raise AssertionError(f"Wasm results: {len(actual)}, expected {len(expected)}")
        index = next(i for i, (a, b) in enumerate(zip(actual, expected)) if a != b)
        raise AssertionError(f"Fixture {index}: WebAssembly {actual[index]}, x86 {expected[index]}")
    report = dict(branch_forms=len(FORMS), segment_reload_forms=len(SEGMENT_FORMS), constant_zero_and_alternate_entry_forms=len(ZERO_FORMS), original_x86_vs_wasm_runs=len(expected),
                  original_gta_functions_compared=1, original_gta_function_runs=len(COUNTERS) * len(FLAGS),
                  original_executable_sha256=cfg["game"]["sha256"],
                  unsupported_segment_states_rejected=rejected,
                  registers_defined_flags_pc_identical=True, original_core_undefined_flags_ignored=["AF after TEST"], game_execution_verified=False,
                  zero_branch_undefined_flags_ignored=["AF after XOR; saved/restored AF is compared"],
                  overlapping_zero_stack_write_comparisons=len(COUNTERS) * len(FLAGS),
                  scope="Synthetic instruction fixtures and one original GTA core function in bounded guest states, not a linked game")
    (ROOT / "build/branch-wasm-status.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
