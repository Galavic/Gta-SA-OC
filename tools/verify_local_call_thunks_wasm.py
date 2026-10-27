"""Execute original local stack-thunk prefixes in x86 and translated Wasm."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tomllib
import argparse

import verify_branch_wasm as B
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EFLAGS, UC_X86_REG_EIP

ROOT, KIT, T = B.ROOT, B.KIT, B.T
STACK = 0x03008000
STACK_LOW, STACK_BYTES = STACK-128, 160
SEEDS = (0x11223300, 0xaabbcc00, 0)


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    binary = ROOT / cfg["game"]["developer_exe"]
    if hashlib.sha256(binary.read_bytes()).hexdigest() != cfg["game"]["sha256"]:
        raise ValueError("Original GTA executable checksum differs")
    image = T.Image(str(binary))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=cfg["translate"]["listings"])
    parser.add_argument("--report", type=Path, default=ROOT / "analysis/local-call-thunks.json")
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if report["executable_sha256"] != cfg["game"]["sha256"]:
        raise ValueError("Local thunk audit belongs to another executable")
    contracts = report["contracts"]
    curated = ROOT / args.input
    curated_check = (curated / "local-call-thunks.json").is_file()
    if curated_check and json.loads((curated / "local-call-thunks.json").read_text()) != report:
        raise ValueError("Curated local prefix provenance differs")
    T.RESUMABLE_STACKS = True
    project, output = ROOT / "build/local-thunk-wasm-project", ROOT / "build/local-thunk-wasm"
    project.mkdir(parents=True, exist_ok=True)
    translated = ['#include "x86.h"']
    for row in contracts:
        start, end = row["callee"], row["end"]
        if image.data[start-image.base:end-image.base].hex() != row["prefix_bytes"]:
            raise ValueError("Original local thunk bytes differ")
        instructions = image.recover(start, set(), bounds=(start, end))
        if curated_check:
            listed = T.parse_listing(str(curated / "functions" / f"{start:08x}.asm"))
            snapshot = lambda seq: [(i.addr, i.mnem, i.rep, tuple(i.ops)) for i in seq]
            if snapshot(listed) != snapshot(instructions):
                raise ValueError("Curated local prefix differs from original instructions")
            instructions = listed
        function = T.Function(start, "original_local_stack_thunk", end-start, instructions)
        function.measure(image)
        tr = T.Translator(image, {start}, B.Opts())
        tr.prepare(function)
        translated.append("\n".join(tr.translate(function)))
    (project / "translated.c").write_text("\n".join(translated), encoding="utf-8")
    harness = r'''#include "x86.h"
#include <stdio.h>
#include <stdlib.h>
uint8_t *g_mem;
uint32_t g_watch_base,g_watch_len;
RecompDirty g_dirty[RECOMP_DIRTY_SLOTS];
uint32_t g_dirty_count;
const int recomp_resumable_stacks=1;
void recomp_watch_hit(uint32_t a,uint32_t n,uint64_t v) { abort(); }
void recomp_callback_return(X86 *c) { abort(); }
int recomp_is_call_return(uint32_t a) { abort(); return 0; }
int recomp_module_is_call_return(uint32_t a) { abort(); return 0; }
int32_t recomp_index_of(uint32_t a) { abort(); return -1; }
int32_t recomp_module_lookup(uint32_t a) { abort(); return -1; }
void recomp_call(X86 *c,uint32_t a) { abort(); }
void recomp_unknown_call(X86 *c,uint32_t a) { abort(); }
void recomp_jump(X86 *c,uint32_t a) { abort(); }
void recomp_unmodelled(X86 *c,uint32_t a) { abort(); }
'''
    harness += "\n".join(f"void fn_{r['callee']:08x}(X86 *c);" for r in contracts)
    harness += "\nint main(void) { g_mem=calloc(1,0x04000000u); if(!g_mem) return 2;\n"
    for row in contracts:
        value = int.from_bytes(bytes.fromhex(row["metadata_bytes"]), "little")
        harness += f"wr32({row['metadata']}u,{value}u);\n"
    checksum_words = {}
    for row in contracts:
        form = row.get("checksum_form")
        if form:
            for index in range(form["words"]):
                address = form["source"] + index*4
                checksum_words[address] = image.rd32(address)
    for address, value in sorted(checksum_words.items()):
        harness += f"wr32({address}u,{value}u);\n"
    harness += "uint32_t seeds[]={" + ",".join(f"{v}u" for v in SEEDS) + "};\n"
    harness += "uint32_t flags[]={" + ",".join(f"{v}u" for v in B.FLAGS) + "};\n"
    harness += f"for(unsigned form=0;form<{len(contracts)};++form) for(unsigned si=0;si<{len(SEEDS)};++si) for(unsigned fi=0;fi<{len(B.FLAGS)};++fi) {{\n"
    harness += f"X86 c={{0}}; for(unsigned j=0;j<8;++j) c.r[j]=seeds[si]+j; c.r[4]={STACK}u; x86_set_eflags(&c,flags[fi]);\n"
    harness += f"for(unsigned j=0;j<{STACK_BYTES};++j) g_mem[{STACK_LOW}u+j]=0xa5;\n"
    harness += "switch(form) {\n"
    for index, row in enumerate(contracts):
        harness += f"case {index}: wr32(c.r[4],{row['original_return']}u); fn_{row['callee']:08x}(&c); break;\n"
    harness += "}\n"
    harness += 'for(unsigned j=0;j<8;++j) printf("%08x ",c.r[j]); printf("%08x %08x ",x86_get_eflags(&c),c.eip);\n'
    harness += f'for(unsigned j=0;j<{STACK_BYTES};++j) printf("%02x",g_mem[{STACK_LOW}u+j]); printf("\\n");\n'
    harness += "} free(g_mem); return 0; }\n"
    (project / "oracle.c").write_text(harness, encoding="utf-8")
    (project / "CMakeLists.txt").write_text(f'''cmake_minimum_required(VERSION 3.24)
project(LocalThunkWasmOracle C)
set(CMAKE_C_STANDARD 11)
add_executable(local_thunk_oracle translated.c oracle.c)
target_include_directories(local_thunk_oracle PRIVATE "{(KIT / 'runtime').as_posix()}")
target_compile_options(local_thunk_oracle PRIVATE -O2)
target_link_options(local_thunk_oracle PRIVATE -O1 "-sENVIRONMENT=node" "-sEXIT_RUNTIME=1" "-sALLOW_MEMORY_GROWTH=1")
''', encoding="utf-8")
    sdk = Path.home() / "GTASAWebToolchains/emsdk"
    os.environ["EMSDK"], os.environ["EM_CONFIG"] = str(sdk), str(sdk / ".emscripten")
    os.environ["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + str(sdk / "upstream/emscripten") + os.pathsep + os.environ.get("PATH", "")
    subprocess.run([B.driver.cmake_tool("cmake"), "-S", str(project), "-B", str(output), "-G", "Ninja",
                    "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_TOOLCHAIN_FILE=" + (sdk / "upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake").as_posix()], check=True)
    B.driver.build("web", ["local_thunk_oracle"], 2, build_dir=output)
    node = next((sdk / "node").glob("*/node.exe"))
    result = subprocess.run([str(node), str(output / "local_thunk_oracle.js")], capture_output=True, text=True, check=True, timeout=60)
    actual = result.stdout.splitlines()
    emulator = Uc(UC_ARCH_X86, UC_MODE_32)
    emulator.mem_map(image.base, (len(image.data)+0xfff)&~0xfff)
    emulator.mem_write(image.base, image.data)
    emulator.mem_map(STACK&~0xffff, 0x10000)
    # Guards reload the Win32 ring-3 SS selector and preserve saved flags.
    emulator.mem_map(0x10000,0x1000)
    descriptors=bytearray(64)
    for slot,descriptor in {1:0x00cf9a000000ffff,2:0x00cf92000000ffff,3:0x00cffa000000ffff,4:0x00cff2000000ffff}.items():
        descriptors[slot*8:slot*8+8]=struct.pack("<Q",descriptor)
    emulator.mem_write(0x10000,bytes(descriptors))
    emulator.reg_write(B.UC_X86_REG_GDTR,(0,0x10000,len(descriptors)-1,0))
    emulator.reg_write(B.UC_X86_REG_CS,8)
    emulator.reg_write(B.UC_X86_REG_SS,16)
    bootstrap=0x02f00000
    emulator.mem_map(bootstrap,0x1000)
    emulator.mem_write(bootstrap,b"\xcf")
    emulator.mem_write(STACK+0x100,struct.pack("<IIIII",contracts[0]["callee"],0x1b,0x202,STACK,0x23))
    emulator.reg_write(B.REGISTERS[4],STACK+0x100)
    emulator.emu_start(bootstrap,contracts[0]["callee"],count=10)
    index = 0
    for row in contracts:
        for seed in SEEDS:
            for flags in B.FLAGS:
                registers = [seed+j for j in range(8)]
                registers[4] = STACK
                for register,value in zip(B.REGISTERS,registers):
                    emulator.reg_write(register,value)
                emulator.reg_write(UC_X86_REG_EFLAGS,flags)
                emulator.mem_write(STACK_LOW,b"\xa5"*STACK_BYTES)
                emulator.mem_write(STACK,struct.pack("<I",row["original_return"]))
                emulator.emu_start(row["callee"],row["destination"],count=50000)
                if emulator.reg_read(UC_X86_REG_EIP) != row["destination"]:
                    raise AssertionError("Original prefix did not take its verified RET4 destination")
                if emulator.reg_read(B.REGISTERS[4]) != STACK or int.from_bytes(emulator.mem_read(STACK,4),"little") != row["changed_continuation"]:
                    raise AssertionError("Original caller's changed continuation/stack shape differs")
                expected = [emulator.reg_read(r) for r in B.REGISTERS]+[emulator.reg_read(UC_X86_REG_EFLAGS),emulator.reg_read(UC_X86_REG_EIP)]
                fields = actual[index].split()
                if [int(x,16) for x in fields[:10]] != expected or fields[10] != bytes(emulator.mem_read(STACK_LOW,STACK_BYTES)).hex():
                    raise AssertionError(f"Original x86/Wasm local prefix differs for call {row['call_site']:x}, seed {seed:x}, flags {flags:x}")
                index += 1
    if index != len(actual):
        raise AssertionError("Unexpected number of local thunk results")
    status = dict(original_local_call_forms=len(contracts), original_x86_vs_wasm_runs=index,
                  curated_input_verified=str(curated) if curated_check else None,
                  registers_flags_pc_stack_identical=True, original_executable_sha256=cfg["game"]["sha256"],
                  game_execution_verified=False,
                  compared_stack_bytes=STACK_BYTES,
                  audit_report_sha256=hashlib.sha256(args.report.read_bytes()).hexdigest(),
                  scope="Original fixed local thunk prefixes in bounded guest states; actual target bodies not executed")
    (ROOT / "build/local-thunk-wasm-status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps(status))


if __name__ == "__main__":
    main()
