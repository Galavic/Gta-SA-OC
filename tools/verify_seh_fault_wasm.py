"""Compare real compiled runtime fault dispatch against actual x86 Windows."""
from pathlib import Path
import json
import os
import subprocess
import sys
import verify_branch_wasm as B

ROOT, KIT, T = B.ROOT, B.KIT, B.T
sys.path.insert(0,str(KIT / "tools/recomp/tests"))
from test_translate_driver import synthetic_image


def main():
    reference=json.loads((ROOT / "build/seh-fault-windows-reference.json").read_text())
    project=ROOT / "build/seh-fault-wasm-project"
    output=ROOT / "build/seh-fault-wasm"
    project.mkdir(exist_ok=True)
    T.RESUMABLE_STACKS=True
    entry=0x00401000
    image=synthetic_image({entry:bytes.fromhex("0f 0b"),entry+16:bytes.fromhex("9c c3")})
    fn=T.Function(entry,"fault_fixture",2,image.recover(entry,set(),bounds=(entry,entry+2)))
    fn.measure(image)
    translator=T.Translator(image,{entry},B.Opts())
    translator.prepare(fn)
    code='#include "x86.h"\n'+"\n".join(translator.translate(fn))
    push=T.Function(entry+16,"pushfd_fixture",2,image.recover(entry+16,set(),bounds=(entry+16,entry+18)))
    push.measure(image)
    translator.prepare(push)
    code+='\nvoid fault_pushfd(X86 *c) {\n'+"\n".join(translator.emit(push,0,T.ALL_FLAGS))+'\n}\n'
    (project / "translated.c").write_text(code,encoding="utf-8")
    subprocess.run([sys.executable,str(KIT / "tools/gen_game_config.py"),"--game-dir",str(ROOT),
                    "--header",str(project / "game_config.h"),"--cmake",str(project / "game.cmake")],check=True)
    sources=[project / "translated.c",ROOT / "tools/seh_fault_wasm.cpp",
             KIT / "runtime/seh.cpp",KIT / "runtime/cpu.cpp",KIT / "runtime/interp.cpp"]
    quoted="\n".join('"'+p.as_posix()+'"' for p in sources)
    (project / "CMakeLists.txt").write_text(f'''cmake_minimum_required(VERSION 3.24)
project(SehFaultOracle C CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(seh_fault_oracle {quoted})
target_include_directories(seh_fault_oracle PRIVATE "{(KIT / 'runtime').as_posix()}" "{project.as_posix()}")
target_compile_definitions(seh_fault_oracle PRIVATE GUEST_SIZE=0x04000000)
target_compile_options(seh_fault_oracle PRIVATE -O1 -fexceptions)
target_link_options(seh_fault_oracle PRIVATE -O1 -fexceptions -sENVIRONMENT=node -sEXIT_RUNTIME=1 -sALLOW_MEMORY_GROWTH=1)
''',encoding="utf-8")
    sdk=Path.home() / "GTASAWebToolchains/emsdk"
    os.environ["EMSDK"],os.environ["EM_CONFIG"]=str(sdk),str(sdk / ".emscripten")
    os.environ["PATH"]=str(ROOT / ".venv/Scripts")+os.pathsep+str(sdk / "upstream/emscripten")+os.pathsep+os.environ.get("PATH","")
    subprocess.run([B.driver.cmake_tool("cmake"),"-S",str(project),"-B",str(output),"-G","Ninja",
                    "-DCMAKE_BUILD_TYPE=Release","-DCMAKE_TOOLCHAIN_FILE="+(sdk / "upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake").as_posix()],check=True)
    B.driver.build("web",["seh_fault_oracle"],2,build_dir=output)
    node=next((sdk / "node").glob("*/node.exe"))
    command=[str(node),str(output / "seh_fault_oracle.js")]
    run=subprocess.run(command,capture_output=True,text=True,check=True,timeout=30)
    actual=json.loads(run.stdout)
    if actual!=reference["results"]:
        (output / "mismatch.json").write_text(json.dumps(dict(actual=actual,reference=reference["results"]),indent=2))
        raise AssertionError("Actual compiled SEH fault path differs from native x86 Windows")
    patched=subprocess.run(command+["patched"],capture_output=True,text=True,check=True,timeout=30)
    if "patched current bytes executed" not in patched.stdout:
        raise AssertionError("Patched UD2 did not use the current guest bytes")
    for resume in ("resume","nested_resume"):
        continued=subprocess.run(command+[resume],capture_output=True,text=True,check=True,timeout=30)
        if "resumable checkpoint unwind verified" not in continued.stdout:
            raise AssertionError("Fault continuation retained an expired host checkpoint")
    for negative in ("context","segment","noncontinuable","debug","unhandled","patched_fault","orphan","legacy"):
        check=subprocess.run(command+[negative],capture_output=True,text=True,timeout=30)
        if check.returncode==0 or check.returncode==4:
            raise AssertionError("Unsupported fault case returned normally: "+negative)
    result=dict(native_windows_vs_wasm_cases=len(actual),integer_registers_control_flags_and_records_identical=True,
                patched_ud2_current_bytes_verified=True,resumable_checkpoint_unwind_cases=2,
                unsupported_cases_aborted=8,game_execution_verified=False,
                scope="Integer/control continuation for UD2 and reanchored registration checkpoints; fixture callback/allocator around actual seh.cpp/cpu.cpp/interp.cpp. Full FPU/debug contexts and game execution are not verified.")
    (ROOT / "build/seh-fault-wasm-status.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result))


if __name__=="__main__":
    main()
