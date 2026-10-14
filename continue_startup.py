"""Continue bounded, audited original-startup rounds without a chat terminal.

Only entries actually refused by the real boot probe are admitted. Any byte
mismatch, unsupported emission, dispatch-gate failure or build error stops
the supervisor. No exclusions, fallback-success values or game edits are made.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STATUS = ROOT / "build/startup-continuation-status.json"
LOCK = ROOT / "build/startup-continuation.lock"
PYTHON = ROOT / ".venv/Scripts/python.exe"


def save(state):
    temporary = STATUS.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(STATUS)


def run(script, *args):
    command = [str(PYTHON), str(ROOT / script), *map(str, args)]
    print("Running:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def supervise(rounds):
    # An exclusive project-owned file prevents two supervisors publishing
    # addons or using the same Ninja build directory concurrently.
    with LOCK.open("x", encoding="utf-8") as lock:
        lock.write(str(os.getpid()))
    state = dict(state="running", pid=os.getpid(), rounds_limit=rounds,
                 started_utc=datetime.now(timezone.utc).isoformat(), rounds=[],
                 gameplay_verified=False)
    save(state)
    try:
        for index in range(rounds):
            run("verify_game_boot.py", "--trace-imports")
            pointer = json.loads((ROOT / "build/boot-probe-last-run.json").read_text())
            probe = json.loads(Path(pointer["status_file"]).read_text())
            target = probe.get("last_target")
            error = probe.get("last_error") or ""
            state["latest_probe"] = pointer["status_file"]
            if (not probe["original_entry"] or not probe["snapshot_complete"] or not target
                    or not any(message in error for message in
                               ("untranslated code at", "no block entry for indirect jump"))):
                state.update(state="needs_review", reason=error or "No audited missing-entry halt")
                break
            snapshot = Path(probe["output_directory"]) / "halt.json"
            proof = ROOT / "build" / ("startup-proof-auto-" + probe["run_id"] + ".json")
            record = dict(index=index + 1, target=target, probe=pointer["status_file"],
                          proof=str(proof), step="audit")
            state["rounds"].append(record)
            save(state)
            run("audit_observed_entry.py", "--snapshot", snapshot, "--out", proof)
            record["step"] = "generate"
            save(state)
            run("build_startup_addon.py", "--generate-only", "--entries", target, "--proof", proof)
            admission = json.loads((ROOT / "startup-addon-manifest.json").read_text())
            record.update(step="build", stage=admission["stage"])
            save(state)
            run("build_startup_addon.py", "--build-only", "--stage", admission["stage"],
                "--targets", "game_boot_probe", "recomp_app", "--jobs", "4")
            record["step"] = "publish"
            save(state)
            run("build.py", "--target", "web", "--jobs", "4", "--diagnostic-all")
            record["step"] = "published"
            save(state)
        else:
            state["state"] = "round_limit_reached"
        # Record the execution after the last publication, not just its build.
        if state["state"] == "round_limit_reached":
            run("verify_game_boot.py", "--trace-imports")
            pointer = json.loads((ROOT / "build/boot-probe-last-run.json").read_text())
            state["latest_probe"] = pointer["status_file"]
    except Exception as error:
        state.update(state="needs_review", reason=str(error))
        print("Stopped for review:", error, flush=True)
    finally:
        state["updated_utc"] = datetime.now(timezone.utc).isoformat()
        save(state)
        LOCK.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.rounds <= 16:
        parser.error("--rounds must be between 1 and 16")
    if LOCK.exists():
        parser.error("A continuation owns the lock; inspect its status and PID first")
    if args.background:
        with (ROOT / "build/startup-continuation.log").open("a", encoding="utf-8") as output:
            child = subprocess.Popen([str(PYTHON), str(Path(__file__).resolve()),
                                      "--rounds", str(args.rounds)], cwd=ROOT,
                                     stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW |
                                                   subprocess.CREATE_NEW_PROCESS_GROUP |
                                                   subprocess.CREATE_BREAKAWAY_FROM_JOB)
        print("Startup continuation supervisor PID", child.pid)
    else:
        supervise(args.rounds)


if __name__ == "__main__":
    main()
