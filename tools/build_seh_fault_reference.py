"""Build and execute a private 32-bit Windows hardware exception reference."""
from pathlib import Path
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    install = Path(subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-property", "installationPath"], text=True).strip())
    vcvars = install / "VC/Auxiliary/Build/vcvars32.bat"
    if not vcvars.is_file() or '"' in str(vcvars):
        raise RuntimeError("32-bit Visual C++ tools are unavailable")
    captured = subprocess.run(f'cmd.exe /d /c call "{vcvars}" >nul && set', capture_output=True, text=True, check=True)
    env = {key.upper():value for key,value in os.environ.items()}
    for line in captured.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            env[key.upper()] = value
    output = ROOT / "build/seh-native-reference"
    output.mkdir(exist_ok=True)
    exe = output / "seh-fault-reference.exe"
    compiler = shutil.which("cl.exe", path=env["PATH"])
    if not compiler:
        raise RuntimeError("Visual C++ did not provide the x86 compiler")
    subprocess.run([compiler, "/nologo", "/W4", "/Od", "/TC", str(ROOT / "tools/seh_fault_native.c"),
                    "/Fo"+str(output / "reference.obj"), "/Fe"+str(exe), "/link", "/MACHINE:X86"], env=env, cwd=output, check=True)
    run = subprocess.run([str(exe)], capture_output=True, text=True, check=True, timeout=30)
    rows = json.loads(run.stdout)
    result = dict(reference="Actual Windows x86 UD2 and continuation through CONTEXT", game_execution_verified=False, results=rows)
    (ROOT / "build/seh-fault-windows-reference.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
