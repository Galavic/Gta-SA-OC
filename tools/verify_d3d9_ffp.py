"""Build and run the bounded fixed-function renderer's actual Wasm tests."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "vendor/recomp-kit"
sys.path.insert(0, str(KIT / "tools"))
import build as driver


def main():
    sdk = Path.home() / "GTASAWebToolchains/emsdk"
    directory = ROOT / "build/cmake/web"
    os.environ["EMSDK"] = str(sdk)
    os.environ["EM_CONFIG"] = str(sdk / ".emscripten")
    os.environ["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + str(sdk / "upstream/emscripten") + os.pathsep + os.environ["PATH"]
    driver.build("web", ["d3d9_ffp_tests"], 4, build_dir=directory)
    node = next((sdk / "node").glob("*/node.exe"))
    result = subprocess.run([str(node), str(ROOT / "build/web/recomp/d3d9_ffp_tests.js")],
                            capture_output=True, text=True, timeout=60,
                            env=dict(os.environ, RECOMP_LOG="1"),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    match = re.search(r"(\d+) checks, (\d+) failures", result.stdout)
    if result.returncode or not match or int(match[2]):
        raise AssertionError("Fixed-function raster checks failed")
    status = dict(checks=int(match[1]), failures=int(match[2]), actual_wasm=True,
                  actual_raster_pixels=True, actual_shader_decoder=True,
                  actual_wgsl_generation=True, actual_gpu_execution=False,
                  game_execution_verified=False, playable_verified=False,
                  scope="bounded unlit/prelit XYZ/XYZRHW fixed function", stdout=result.stdout)
    (ROOT / "build/d3d9-ffp-wasm-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
