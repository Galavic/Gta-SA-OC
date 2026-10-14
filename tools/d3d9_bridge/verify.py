"""Verify guest vertex parsing on real x86 Windows SDK and actual WebAssembly."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import hashlib
import pefile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "build/d3d9-bridge-vertex"


def main():
    OUT.mkdir(exist_ok=True)
    game_path = ROOT / "prepared/gta_sa.exe"
    game_bytes = game_path.read_bytes()
    game_sha = hashlib.sha256(game_bytes).hexdigest()
    if game_sha != "cd885d84bcbdacddc27bdbd6676e376557f118f090e71e0db7c746e72c949064":
        raise AssertionError("Original executable identity mismatch")
    pe = pefile.PE(data=game_bytes)
    base = pe.OPTIONAL_HEADER.ImageBase
    # Actual native MOV ECX,0x252 and COM SetFVF call through guest slot89.
    evidence = {0x814ddc: bytes.fromhex("b952020000"),
                0x814e01: bytes.fromhex("ff9264010000")}
    for address, expected in evidence.items():
        if pe.get_data(address-base,len(expected)) != expected:
            raise AssertionError(f"Native FVF evidence mismatch at {address:08x}")
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    install = Path(subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-property", "installationPath"], text=True).strip())
    vcvars = install / "VC/Auxiliary/Build/vcvars32.bat"
    captured = subprocess.run(f'cmd.exe /d /c call "{vcvars}" >nul && set', capture_output=True, text=True, check=True)
    env = {key.upper(): value for key, value in os.environ.items()}
    for line in captured.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            env[key.upper()] = value
    compiler = shutil.which("cl.exe", path=env["PATH"])
    if not compiler:
        raise RuntimeError("x86 MSVC compiler unavailable")
    exe = OUT / "fixture.exe"
    subprocess.run([compiler, "/nologo", "/W4", "/WX", "/EHsc", "/std:c++17", str(HERE / "fixture.cpp"),
                    "/Fo" + str(OUT / "fixture.obj"), "/Fe" + str(exe), "/link", "/MACHINE:X86"],
                   env=env, cwd=OUT, check=True)
    native = json.loads(subprocess.check_output([str(exe)], text=True, timeout=30))
    toolchain = Path.home() / "GTASAWebToolchains/emsdk"
    empp = toolchain / "upstream/emscripten/em++.exe"
    node_candidates = list((toolchain / "node").glob("*/node.exe"))
    if not node_candidates:
        raise RuntimeError("Emscripten Node executable unavailable")
    javascript = OUT / "fixture.js"
    subprocess.run([str(empp), "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O1",
                    str(HERE / "fixture.cpp"), "-sENVIRONMENT=node", "-sEXIT_RUNTIME=1",
                    "-o", str(javascript)], cwd=OUT, check=True, timeout=120)
    wasm = json.loads(subprocess.check_output([str(node_candidates[-1]), str(javascript)], text=True, timeout=30))
    if native != wasm:
        raise AssertionError(f"Windows/Wasm mismatch: {native} != {wasm}")
    status = {"passed": True, "native_windows_x86_sdk_verified": True, "wasm_verified": True,
              "results": wasm, "game_execution_verified": False,
              "original_exe_sha256": game_sha,
              "native_fvf_evidence": {"mov_ecx_address": "00814ddc", "fvf": "00000252",
                                      "call_address": "00814e01", "guest_vtable_offset": "00000164",
                                      "decoded_stride_bytes": 44},
              "sdk_abi": {"IDirect3D9_CreateDevice_slot": 16, "IDirect3DDevice9_Clear_slot": 43,
                          "IDirect3DDevice9_DrawPrimitiveUP_slot": 83, "IDirect3DDevice9_SetFVF_slot": 89,
                          "D3DPRESENT_PARAMETERS_bytes": 56, "D3DLOCKED_RECT_bytes": 8,
                          "D3DVERTEXELEMENT9_bytes": 8}}
    (ROOT / "build/d3d9-bridge-vertex-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
