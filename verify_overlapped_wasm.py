"""Compile actual file-read shim bodies into Wasm and compare native Windows.

The small host supplies test handles/events and libc file descriptors, not a
game runtime. Original assets are untouched and no game linkage is claimed.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import verify_branch_wasm as B
from audit_overlapped_windows import main as audit_windows

ROOT, KIT = B.ROOT, B.KIT


def main():
    audit_windows()
    reference = json.loads((ROOT / "build/overlapped-windows-reference.json").read_text())["cases"]
    source = (KIT / "runtime/kernel32.cpp").read_text(encoding="utf-8")
    bodies = []
    for name in ("file_read_complete", "k_ReadFile", "k_GetOverlappedResult"):
        match = re.search(r"^(?:static )?void " + name + r"\([^\n]*\)\s*\{.*?^\}", source, re.M | re.S)
        if not match:
            raise ValueError("Actual file shim body not found: " + name)
        bodies.append(match[0])
    project, output = ROOT / "build/overlapped-wasm-project", ROOT / "build/overlapped-wasm"
    project.mkdir(parents=True, exist_ok=True)
    harness = r'''#include "imports.h"
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
uint8_t *g_mem;
uint32_t g_watch_base, g_watch_len;
RecompDirty g_dirty[RECOMP_DIRTY_SLOTS];
uint32_t g_dirty_count;
uint32_t error_code;
void recomp_watch_hit(uint32_t a, uint32_t n, uint64_t v) { abort(); }
void recomp_unmodelled(X86 *c, uint32_t a) { abort(); }
enum HKind { H_FILE=1, H_EVENT=4, H_STD=10 };
struct HObj { int fd=-1; bool file_overlapped=false; bool signalled=false; };
HObj file, event;
HObj *handle_get(uint32_t h,HKind kind) {
    if(h==1 && kind==H_FILE) return &file;
    if(h==2 && kind==H_EVENT) return &event;
    return nullptr;
}
void set_last_error(uint32_t e) { error_code=e; }
bool win32_reset_event(uint32_t h) { if(h!=2) return false; event.signalled=false; return true; }
bool win32_signal_event(uint32_t h,bool pulse) { if(h!=2) return false; event.signalled=!pulse; return true; }
void sched_wake_all() {}
const char *recomp_env(const char *s) { return nullptr; }
enum { ERROR_INVALID_HANDLE_=6, ERROR_ACCESS_DENIED_=5, OS_SEEK_CUR=SEEK_CUR, OS_SEEK_SET=SEEK_SET };
int64_t os_fd_seek(int fd,int64_t off,int whence) { return (int64_t)lseek(fd,(off_t)off,whence); }
int64_t os_fd_read(int fd,void *buf,size_t n) { return (int64_t)read(fd,buf,n); }
#undef LOGW
#define LOGW(...) do {} while(0)
'''
    harness += "\n".join(bodies)
    harness += r'''
int main() {
    g_mem=(uint8_t*)calloc(1,0x01000000u); if(!g_mem) return 2;
    FILE *f=fopen("reference.bin","wb"); if(!f) return 3;
    fwrite("0123456789abcdef\n",1,17,f); fclose(f);
    file.fd=open("reference.bin",O_RDONLY); if(file.fd<0) return 4;
    uint64_t offsets[]={0,3,16,17,18,0x100000000ull};
    uint32_t sizes[]={0,1,4,100};
    const uint32_t sp=0x00600000u,buf=0x00500000u,over=0x00400000u,count=over+32,done=over+36;
    for(unsigned async=0;async<2;++async) for(uint64_t offset:offsets) for(uint32_t size:sizes) {
        file.file_overlapped=async!=0;
        lseek(file.fd,3,SEEK_SET); memset(g_mem+over,0,64); memset(g_mem+buf,0,100);
        wr32(over+8,(uint32_t)offset); wr32(over+12,(uint32_t)(offset>>32)); wr32(over+16,2);
        wr32(count,0x55555555); wr32(done,0xaaaaaaaa);
        X86 c={}; c.r[4]=sp;
        wr32(sp+4,1); wr32(sp+8,buf); wr32(sp+12,size); wr32(sp+16,count); wr32(sp+20,over);
        error_code=0; k_ReadFile(&c);
        printf("%u %u %u ",c.r[0],error_code,rd32(count));
        wr32(sp+4,1); wr32(sp+8,over); wr32(sp+12,done); wr32(sp+16,1);
        error_code=0; k_GetOverlappedResult(&c);
        printf("%u %u %u %u %u %lld %u ",c.r[0],error_code,rd32(done),rd32(over),rd32(over+4),
               (long long)lseek(file.fd,0,SEEK_CUR),event.signalled ? 1u : 0u);
        if(c.r[0]) for(unsigned j=0;j<rd32(done);++j) printf("%02x",g_mem[buf+j]);
        printf("\n");
    }
    close(file.fd); free(g_mem); return 0;
}
'''
    (project / "oracle.cpp").write_text(harness, encoding="utf-8")
    subprocess.run([sys.executable, str(KIT / "tools/gen_game_config.py"), "--game-dir", str(ROOT),
                    "--header", str(project / "game_config.h"), "--cmake", str(project / "game_config.cmake")], check=True)
    (project / "CMakeLists.txt").write_text(f'''cmake_minimum_required(VERSION 3.24)
project(OverlappedWasmOracle CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(overlapped_oracle oracle.cpp)
target_include_directories(overlapped_oracle PRIVATE "{(KIT / 'runtime').as_posix()}")
target_compile_definitions(overlapped_oracle PRIVATE GUEST_MEM_SIZE=0x01000000u)
target_compile_options(overlapped_oracle PRIVATE -O2)
target_link_options(overlapped_oracle PRIVATE "-sENVIRONMENT=node" "-sEXIT_RUNTIME=1" "-sALLOW_MEMORY_GROWTH=1")
add_library(runtime_io_objects OBJECT "{(KIT / 'runtime/kernel32.cpp').as_posix()}" "{(KIT / 'runtime/cpu.cpp').as_posix()}")
target_include_directories(runtime_io_objects PRIVATE "{project.as_posix()}" "{KIT.as_posix()}" "{(KIT / 'runtime').as_posix()}")
target_compile_definitions(runtime_io_objects PRIVATE GUEST_SIZE=0x20000000u GUEST_IMAGE_BASE=0x00400000u GUEST_HEAP_BASE=0x02500000u)
target_compile_options(runtime_io_objects PRIVATE -O2 -pthread -fno-strict-aliasing)
''', encoding="utf-8")
    sdk = Path.home() / "GTASAWebToolchains/emsdk"
    os.environ["EMSDK"], os.environ["EM_CONFIG"] = str(sdk), str(sdk / ".emscripten")
    os.environ["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + str(sdk / "upstream/emscripten") + os.pathsep + os.environ.get("PATH", "")
    subprocess.run([B.driver.cmake_tool("cmake"), "-S", str(project), "-B", str(output), "-G", "Ninja",
                    "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_TOOLCHAIN_FILE=" + (sdk / "upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake").as_posix()], check=True)
    B.driver.build("web", ["overlapped_oracle", "runtime_io_objects"], 2, build_dir=output)
    node = next((sdk / "node").glob("*/node.exe"))
    result = subprocess.run([str(node), str(output / "overlapped_oracle.js")], capture_output=True, text=True, check=True)
    actual = result.stdout.splitlines()
    if len(actual) != len(reference):
        raise AssertionError("Unexpected number of file-I/O results")
    for index, (line, native) in enumerate(zip(actual, reference)):
        fields = line.split()
        values = list(map(int, fields[:10]))
        expected = [int(native["readfile_success"]), native["readfile_error"], native["readfile_count"],
                    int(native["completed"]), native["completed_error"], native["transferred"],
                    native["internal_status"], native["internal_count"], native["final_file_position"],
                    int(native["event_signalled"])]
        if values != expected or (fields[10] if len(fields)>10 else "") != native["bytes"]:
            raise AssertionError(f"Case {index}: Wasm {line}; Windows {native}")
    report = dict(native_windows_vs_wasm_cases=len(actual), actual_shim_source_compiled=True,
                  full_kernel32_and_cpu_wasm_objects_compiled=True,
                  bytes_counts_offsets_status_file_position_events_identical=True,
                  game_execution_verified=False,
                  scope="Actual ReadFile/GetOverlappedResult bodies, fixture handles/events and libc descriptors; not complete runtime or game")
    (ROOT / "build/overlapped-wasm-status.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
