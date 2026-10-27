"""Compile translated original audio modules to WebAssembly object archives.

These are libraries, not a linked game or proof of working sound. Generated C
is compiled unchanged, through the kit's build driver and the local web SDK.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "vendor/recomp-kit"
sys.path.insert(0, str(KIT / "tools"))
spec = importlib.util.spec_from_file_location("kit_build", KIT / "tools/build.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def wasm_members(path):
    data = path.read_bytes()
    if data[:8] != b"!<arch>\n":
        raise ValueError("Compiler output is not an archive")
    cursor, count = 8, 0
    while cursor < len(data):
        header = data[cursor:cursor + 60]
        if len(header) != 60 or header[58:] != b"`\n":
            raise ValueError("Invalid archive member")
        size = int(header[48:58])
        payload = data[cursor + 60:cursor + 60 + size]
        if len(payload) != size:
            raise ValueError("Truncated archive member")
        if payload[:8] == b"\0asm\x01\0\0\0":
            count += 1
        cursor += 60 + size + (size & 1)
    if not count:
        raise ValueError("Archive contains no WebAssembly object")
    return count


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    sdk = Path.home() / "GTASAWebToolchains/emsdk"
    os.environ["EMSDK"] = str(sdk)
    os.environ["EM_CONFIG"] = str(sdk / ".emscripten")
    os.environ["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + str(sdk / "upstream/emscripten") + os.pathsep + os.environ.get("PATH", "")
    project, output = ROOT / "build/audio-cmake-project", ROOT / "build/audio-wasm"
    project.mkdir(exist_ok=True)
    lines = ["cmake_minimum_required(VERSION 3.24)", "project(GTASAOriginalAudio C)", "set(CMAKE_C_STANDARD 11)"]
    targets = []
    for key in cfg["modules"]["aux"]:
        source = ROOT / "build/audio-probe" / key
        sources = sorted(source.glob("chunk_*.c")) + [source / "table.c"]
        if not all(p.is_file() for p in sources) or len(sources) < 2:
            raise ValueError("Strict audio translation is missing")
        target = "recomp_gen_" + key
        targets.append(target)
        paths = " ".join(f'"{p.as_posix()}"' for p in sources)
        lines.extend([f"add_library({target} STATIC {paths})", f'target_include_directories({target} PRIVATE "{source.as_posix()}" "{KIT.as_posix()}" "{(KIT / "runtime").as_posix()}")', f"target_compile_definitions({target} PRIVATE GUEST_SIZE=0x20000000u GUEST_IMAGE_BASE=0x00400000u GUEST_HEAP_BASE=0x02500000u)", f"target_compile_options({target} PRIVATE -O2 -pthread -fno-strict-aliasing)"])
    (project / "CMakeLists.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    toolchain = sdk / "upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake"
    subprocess.run([driver.cmake_tool("cmake"), "-S", str(project), "-B", str(output), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_TOOLCHAIN_FILE=" + toolchain.as_posix()], check=True)
    driver.build("web", targets, 2, build_dir=output)
    archives = [dict(module=key, archive=str(output / ("librecomp_gen_" + key + ".a")), wasm_objects=wasm_members(output / ("librecomp_gen_" + key + ".a"))) for key in cfg["modules"]["aux"]]
    report = dict(compiler="Emscripten 6.0.12", linked_game=False, audio_execution_verified=False, archives=archives)
    (ROOT / "build/audio-wasm-status.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
