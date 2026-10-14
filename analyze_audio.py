"""Export assembly from the verified rebased original audio DLL copies."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    prepared = ROOT / "build/relocated-audio"
    report = json.loads((prepared / "preparation.json").read_text())
    paths = json.loads((ROOT / "analysis/toolchain.json").read_text())
    ghidra, java = Path(paths["ghidra"]), Path(paths["jdk"])
    env = dict(os.environ)
    env["JAVA_HOME"] = str(java)
    env["PATH"] = str(java / "bin") + os.pathsep + env.get("PATH", "")
    project = ROOT / "analysis/audio-ghidra-project"
    project.mkdir(exist_ok=True)
    results = []
    for module in report["modules"]:
        binary = prepared / module["name"]
        if hashlib.sha256(binary.read_bytes()).hexdigest() != module["prepared_sha256"]:
            raise ValueError("Prepared audio module changed")
        log = ROOT / "analysis" / (module["name"] + "-analysis.log")
        command = [str(ghidra / "support/analyzeHeadless.bat"), str(project), "GTASAAudio", "-import", str(binary), "-overwrite", "-analysisTimeoutPerFile", "600", "-max-cpu", "2", "-scriptPath", str(ROOT / "tools"), "-preScript", "ConfigureAssemblyAnalysis.java", "-postScript", "ExportAssembly.java", str(ROOT / "analysis")]
        print(f"Analyzing {module['name']} at {module['base']}; log: {log}", flush=True)
        with log.open("w", encoding="utf-8") as output:
            subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, check=True)
        result = json.loads((ROOT / "analysis" / module["name"] / "assembly-summary.json").read_text())
        if not result["functions"]:
            raise ValueError("No audio module functions exported")
        results.append(dict(name=module["name"], sha256=module["prepared_sha256"], base=module["base"], **result))
        print(results[-1], flush=True)
    (ROOT / "analysis/audio-inputs.json").write_text(json.dumps(dict(runtime_verified=False, modules=results), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
