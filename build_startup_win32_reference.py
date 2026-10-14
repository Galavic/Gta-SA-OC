"""Measure startup Win32 contracts on the actual Windows x86 host."""
from pathlib import Path
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    install = Path(subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-property", "installationPath"], text=True).strip())
    vcvars = install / "VC/Auxiliary/Build/vcvars32.bat"
    if not vcvars.is_file() or '"' in str(vcvars):
        raise RuntimeError("32-bit Visual C++ tools are unavailable")
    captured = subprocess.run(f'cmd.exe /d /c call "{vcvars}" >nul && set', capture_output=True, text=True, check=True)
    env = {key.upper(): value for key, value in os.environ.items()}
    for line in captured.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            env[key.upper()] = value
    output = ROOT / "build/startup-win32-native"
    output.mkdir(parents=True, exist_ok=True)
    exe = output / "startup-win32-reference.exe"
    compiler = shutil.which("cl.exe", path=env["PATH"])
    if not compiler:
        raise RuntimeError("Visual C++ did not provide the x86 compiler")
    subprocess.run([compiler, "/nologo", "/W4", "/Od", "/Oy-", "/TC", str(ROOT / "tools/startup_win32_native.c"),
                    "/Fo" + str(output / "reference.obj"), "/Fe" + str(exe), "/link", "/MACHINE:X86"],
                   env=env, cwd=output, check=True)
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    rows = json.loads(run.stdout)
    result = dict(
        reference="Actual Windows x86 startup API contracts",
        game_execution_verified=False,
        feature_policy="Host features are observational only. The guest reports FPU/TSC/CMOV through CPUID and one CPU through GetSystemInfo; feature-query answers must match guest capabilities, not modern host SSE/AVX capabilities.",
        spin_policy="A uniprocessor system may store zero spin count. This fixture measures the actual host system processor count, without claiming single-CPU guest equivalence.",
        results=rows,
    )
    (ROOT / "build/startup-win32-native-reference.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if run.returncode:
        raise RuntimeError(f"Native reference checks failed: {run.returncode}")


if __name__ == "__main__":
    main()
