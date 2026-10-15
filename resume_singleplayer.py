"""Resume the isolated image's translation without rerunning Ghidra."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VARIANT = ROOT / "variants/singleplayer"
STATUS = VARIANT / "analysis-status.json"
LOG = VARIANT / "translation-resume.log"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    if args.background:
        with LOG.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "-u", str(Path(__file__).resolve())], cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW |
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_BREAKAWAY_FROM_JOB,
            )
        print(f"Translation supervisor PID {process.pid}; log: {LOG}")
        return
    state = json.loads(STATUS.read_text(encoding="utf-8"))
    if state.get("state") == "translating":
        # Two translations writing build/recomp/gen at once interleave chunks
        # and resurrect stale bodies as duplicate symbols; refuse instead.
        try:
            os.kill(state["pid"], 0)
        except OSError:
            pass
        else:
            raise SystemExit(f"Translation already running (PID {state['pid']}); refusing a second writer")
    output = VARIANT / "build/recomp"
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", str(ROOT / "vendor/recomp-kit/tools/recomp/translate.py"),
               "--game", str(VARIANT), "--out", str(output / "gen"),
               "--report", str(output / "translate-report.json")]
    state.update(state="translating", pid=os.getpid(), translation_command=command,
                 started_utc=datetime.now(timezone.utc).isoformat(),
                 reason="User requested original engine and 1:1 behavior", gameplay_verified=False)
    state.pop("error", None)
    STATUS.write_text(json.dumps(state, indent=2), encoding="utf-8")
    try:
        # Capture explicitly: the Windows Store Python launcher can replace
        # inherited console handles when it starts the actual interpreter.
        process = subprocess.Popen(command, cwd=ROOT / "vendor/recomp-kit",
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace",
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        for line in process.stdout:
            print(line, end="", flush=True)
        code = process.wait()
        state.update(state="translated_unbuilt" if code == 0 else "needs_review",
                     translation_exit_code=code)
    except Exception as error:
        state.update(state="needs_review", error=str(error))
    finally:
        state["updated_utc"] = datetime.now(timezone.utc).isoformat()
        STATUS.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("Translation status:", state["state"], flush=True)

if __name__ == "__main__":
    main()
