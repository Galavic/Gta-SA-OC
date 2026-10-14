"""Build the real interpreter tests through the kit and execute them in Node."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools"))
import build as driver


def main():
    sdk = Path.home() / "GTASAWebToolchains/emsdk"
    os.environ["EMSDK"] = str(sdk)
    os.environ["EM_CONFIG"] = str(sdk / ".emscripten")
    os.environ["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + str(sdk / "upstream/emscripten") + os.pathsep + os.environ["PATH"]
    driver.build("web", ["interp_tests"], 2, build_dir=ROOT / "build/cmake/web")
    node = next((sdk / "node").glob("*/node.exe"))
    run = subprocess.run([str(node), str(ROOT / "build/web/recomp/interp_tests.js")],
                         capture_output=True, text=True, check=True, timeout=60)
    match = re.search(r"interp: (\d+) checks, (\d+) failures", run.stdout)
    if not match or int(match[2]):
        raise AssertionError(run.stdout + run.stderr)
    negative = subprocess.run([str(node), str(ROOT / "build/web/recomp/interp_tests.js"), "--strict-fault"],
                              capture_output=True, text=True, timeout=30)
    assert negative.returncode != 0
    assert "refusing to skip guest code" in negative.stderr
    assert "[strict-fault] target=01000000 eax=00000005 esp=0dfffef8" in negative.stderr
    assert "FAIL strict fault returned" not in negative.stderr
    status = dict(checks=int(match[1]), failures=int(match[2]), actual_interpreter=True,
                  strict_partial_fault_refused=True,
                  strict_fault_stderr=negative.stderr,
                  game_execution_verified=False, stdout=run.stdout, stderr=run.stderr)
    (ROOT / "build/interp-wasm-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(run.stdout, end="")
    print("Strict partial-execution fault refused; guest EAX preserved before abort")


if __name__ == "__main__":
    main()
