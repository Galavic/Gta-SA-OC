"""Build and execute real Win32 startup-shim tests without loading the game."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
KIT = ROOT / "vendor/recomp-kit"
sys.path.insert(0, str(KIT / "tools"))
import build as driver


def main():
    sdk = Path.home() / "GTASAWebToolchains/emsdk"
    directory = ROOT / "build/cmake/web"
    if not (directory / "build.ninja").exists():
        raise RuntimeError("Build the real web target first to configure this game's runtime")
    os.environ["EMSDK"] = str(sdk)
    os.environ["EM_CONFIG"] = str(sdk / ".emscripten")
    os.environ["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + str(sdk / "upstream/emscripten") + os.pathsep + os.environ["PATH"]
    driver.build("web", ["startup_win32_tests"], 4, build_dir=directory)
    node = next((sdk / "node").glob("*/node.exe"))
    test_env = dict(os.environ, RECOMP_LOG="1")
    hidden = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run([str(node), str(ROOT / "build/web/recomp/startup_win32_tests.js")],
                            capture_output=True, text=True, check=True, timeout=60,
                            env=test_env, creationflags=hidden)
    match = re.search(r"(\d+) checks, (\d+) failures", result.stdout)
    if not match or int(match[2]) != 0:
        raise AssertionError(result.stdout + result.stderr)
    refused = subprocess.run([str(node), str(ROOT / "build/web/recomp/startup_win32_tests.js"),
                              "--strict-unknown"], capture_output=True, text=True, timeout=60,
                              env=test_env, creationflags=hidden)
    assert refused.returncode != 0
    assert "refusing to skip untranslated code at 01000000" in refused.stderr
    assert "unexpected strict return" not in refused.stdout
    for mode, name, reason in [
        ("--strict-import", "MissingImplementation", "no implementation"),
        ("--strict-import-signature", "UnknownConvention", "unknown calling convention"),
    ]:
        refused_import = subprocess.run(
            [str(node), str(ROOT / "build/web/recomp/startup_win32_tests.js"), mode],
            capture_output=True, text=True, timeout=60,
            env=test_env, creationflags=hidden)
        assert refused_import.returncode != 0
        assert f"strict imports: refusing strict-import-test.dll!{name} ({reason})" in refused_import.stderr
        assert "unexpected strict import return" not in refused_import.stdout + refused_import.stderr
        assert "unexpected strict import implementation" not in refused_import.stdout + refused_import.stderr
    status = dict(checks=int(match[1]), failures=int(match[2]),
                  actual_runtime=True, actual_import_dispatch=True,
                  game_execution_verified=False, strict_unknown_refusal_verified=True,
                  strict_import_implementation_refusal_verified=True,
                  strict_import_signature_refusal_verified=True,
                  stdout=result.stdout)
    (ROOT / "build/startup-win32-wasm-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(result.stdout, end="")


if __name__ == "__main__":
    main()
