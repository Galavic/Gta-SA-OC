"""Invoke the kit's real translation/build pipeline with a local web SDK.

No stub targets or permissions to discard unmodelled instructions are added.
Failures are retained in the log rather than treated as a successful port.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("gen", "web"), default="web")
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--background", action="store_true",
                        help="Keep the build supervisor independent of the chat terminal")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--low-opt-chunks", nargs="*", default=[])
    parser.add_argument("--diagnostic-chunks", nargs="*", default=[])
    parser.add_argument("--diagnostic-all", action="store_true")
    parser.add_argument("--emsdk", type=Path, default=Path.home() / "GTASAWebToolchains/emsdk")
    args = parser.parse_args()
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + env.get("PATH", "")
    if args.target == "web":
        sdk = args.emsdk.resolve()
        for required in (".emscripten", "upstream/emscripten/emcc.py"):
            if not (sdk / required).is_file():
                parser.error(f"Emscripten SDK missing {required}: {sdk}")
        env["EMSDK"] = str(sdk)
        env["EM_CONFIG"] = str(sdk / ".emscripten")
        env["PATH"] = str(sdk / "upstream/emscripten") + os.pathsep + env["PATH"]
    if args.background:
        (ROOT / "build").mkdir(exist_ok=True)
        status_path = ROOT / "build" / (args.target + "-status.json")
        if status_path.is_file() and json.loads(status_path.read_text())["state"] == "running":
            parser.error("A build is already marked running; verify its completion before launching another")
        runner_log = ROOT / "build" / (args.target + "-runner.log")
        runner_args = [arg for arg in sys.argv[1:] if arg != "--background"]
        with runner_log.open("w", encoding="utf-8") as output:
            runner = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), *runner_args],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
        print(f"Background supervisor PID {runner.pid}; output: {runner_log}")
        sys.exit(0)
    command = [
        str(ROOT / ".venv/Scripts/python.exe"),
        str(ROOT / "vendor/recomp-kit/tools/build.py"), "--game-dir", str(ROOT),
        "--target", args.target, "--jobs", str(args.jobs),
    ]
    if args.regenerate:
        command.append("--regenerate")
    if args.low_opt_chunks:
        command.extend(["--low-opt-chunks", *args.low_opt_chunks])
    if args.diagnostic_chunks:
        command.extend(["--diagnostic-chunks", *args.diagnostic_chunks])
    if args.diagnostic_all:
        command.append("--diagnostic-all")
    (ROOT / "build").mkdir(exist_ok=True)
    config = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    context = {"listings": config["translate"]["listings"], "supervisor_pid": os.getpid()}
    context["diagnostic_chunks"] = args.diagnostic_chunks
    context["diagnostic_all"] = args.diagnostic_all
    review_path = ROOT / "analysis/quarantine-handoff-review.json"
    if review_path.is_file():
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if Path(review["current"]).resolve() == (ROOT / context["listings"]).resolve():
            context["exclusion_safety_proven"] = review["exclusion_safety_proven"]
            context["exclusion_review"] = str(review_path)
    log = ROOT / "build" / (args.target + "-build.log")
    print(f"Running strict {args.target} pipeline. Log: {log}", flush=True)
    (ROOT / "build" / (args.target + "-status.json")).write_text(json.dumps({
        "target": args.target, "state": "running", "exit_code": None,
        "log": str(log), "playable_verified": False, "stub": False,
        **context,
    }, indent=2), encoding="utf-8")
    with log.open("w", encoding="utf-8") as output:
        result = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode == 0 and args.target == "web":
            result = subprocess.run(
                [sys.executable, str(ROOT / "prepare_browser_wasm.py"), "--emsdk", str(args.emsdk)],
                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
            )
    status = {
        "target": args.target, "state": "finished", "exit_code": result.returncode, "log": str(log),
        "playable_verified": False, "stub": False,
        **context,
    }
    (ROOT / "build" / (args.target + "-status.json")).write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(f"Pipeline exited {result.returncode}; gameplay has not been verified.", flush=True)
    if result.returncode:
        print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]))
    sys.exit(result.returncode)
