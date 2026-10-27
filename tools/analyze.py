"""Analyze the hash-pinned original PE with Ghidra and export runtime inputs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    exe = ROOT / cfg["game"]["developer_exe"]
    with exe.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != cfg["game"]["sha256"]:
        sys.exit("Executable changed; analysis refused")
    paths = json.loads((ROOT / "analysis/toolchain.json").read_text())
    ghidra, java = Path(paths["ghidra"]), Path(paths["jdk"])
    env = dict(os.environ)
    env["JAVA_HOME"] = str(java)
    env["PATH"] = str(java / "bin") + os.pathsep + env.get("PATH", "")
    # Headless only. Save the analysis project for later recovery; no GUI opens.
    project = ROOT / "analysis/ghidra-project"
    project.mkdir(exist_ok=True)
    command = [
        str(ghidra / "support/analyzeHeadless.bat"), str(project), "GTASAOriginal",
        "-import", str(exe), "-overwrite", "-analysisTimeoutPerFile", "600",
        "-max-cpu", "4", "-scriptPath", str(ROOT / "tools"),
        "-preScript", "ConfigureAssemblyAnalysis.java",
        "-postScript", "ExportAssembly.java", str(ROOT / "analysis"),
        "-log", str(ROOT / "analysis/ghidra-analysis.log"),
        "-scriptlog", str(ROOT / "analysis/ghidra-export.log"),
    ]
    print("Analyzing verified original executable; log: analysis/ghidra-analysis.log", flush=True)
    subprocess.run(command, env=env, check=True)
    summary = ROOT / "analysis" / exe.name / "assembly-summary.json"
    if not summary.is_file():
        sys.exit("Assembly export failed; inspect Ghidra logs")
    result = json.loads(summary.read_text())
    if not result["functions"]:
        sys.exit("No functions exported; translation cannot proceed")
    (ROOT / "analysis/inputs.json").write_text(json.dumps({
        "sha256": digest, "ghidra_version": "12.1.3",
        "automatic_analysis": True, "complete_function_recovery_proven": False,
        "summary": result,
    }, indent=2), encoding="utf-8")
    print(result, flush=True)
