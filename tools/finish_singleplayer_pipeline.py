"""Continue to the Wasm build only after the current strict translation succeeds."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VARIANT = ROOT / "variants/singleplayer"
STATUS = VARIANT / "pipeline-status.json"
LOG = VARIANT / "pipeline.log"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    if args.background:
        with LOG.open("a", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve())],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP |
                              subprocess.CREATE_BREAKAWAY_FROM_JOB)
        print(f"Wasm continuation supervisor PID {process.pid}; log: {LOG}")
        return
    state = dict(state="waiting_for_translation", pid=os.getpid(), playable_verified=False,
                 started_utc=datetime.now(timezone.utc).isoformat())
    def save():
        STATUS.write_text(json.dumps(state, indent=2), encoding="utf-8")
    save()
    try:
        while True:
            translation = json.loads((VARIANT / "analysis-status.json").read_text(encoding="utf-8"))
            if translation["state"] != "translating":
                break
            time.sleep(10)
        if translation["state"] != "translated_unbuilt":
            state.update(state="translation_needs_review", translation_state=translation["state"])
            return
        report = json.loads((VARIANT / "build/recomp/translate-report.json").read_text())
        assert not report["failures"] and not report["unmodelled"]
        assert not report["table_gaps"] and not report["table_sites_undecoded"]
        assert not report["unmodelled_allowed"] and not report["table_gaps_allowed"]
        # These four audio DLLs are exactly the same prepared binaries. Reuse
        # their completed source translations, but never the old game's code.
        old = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
        current = tomllib.loads((VARIANT / "game.toml").read_text(encoding="utf-8"))
        reused = []
        for key, module in current["modules"]["aux"].items():
            previous = old["modules"]["aux"][key]
            for field in ("name", "sha256", "base", "size", "function_alignment"):
                assert module[field] == previous[field], (key, field)
            assert hashlib.sha256((VARIANT / module["path"]).read_bytes()).hexdigest() == module["sha256"]
            assert hashlib.sha256((ROOT / previous["path"]).read_bytes()).hexdigest() == module["sha256"]
            audio = json.loads((ROOT / f"build/recomp/translate-{key}-report.json").read_text())
            assert not audio["failures"] and not audio["unmodelled"]
            assert not audio["table_gaps"] and not audio["table_sites_undecoded"]
            source = ROOT / f"build/recomp/gen/aux-{key}"
            assert (source / "table.c").is_file()
            shutil.copytree(source, VARIANT / f"build/recomp/gen/aux-{key}", dirs_exist_ok=True)
            reused.append(key)
        state.update(state="building_wasm", reused_audio_modules=reused)
        save()
        sdk = Path.home() / "GTASAWebToolchains/emsdk"
        assert (sdk / ".emscripten").is_file()
        env = dict(os.environ, EMSDK=str(sdk), EM_CONFIG=str(sdk / ".emscripten"), PYTHONUTF8="1")
        env["PATH"] = os.pathsep.join([str(ROOT / ".venv/Scripts"),
                                       str(sdk / "upstream/emscripten"), env.get("PATH", "")])
        command = [sys.executable, "-u", str(ROOT / "vendor/recomp-kit/tools/build.py"),
                   "--game-dir", str(VARIANT), "--target", "web", "--jobs", "4", "--diagnostic-all"]
        process = subprocess.Popen(command, cwd=ROOT / "vendor/recomp-kit", env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace",
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        for line in process.stdout:
            print(line, end="", flush=True)
        code = process.wait()
        state.update(state="wasm_built_unverified" if code == 0 else "build_needs_review", build_exit_code=code)
    except Exception as error:
        state.update(state="needs_review", error=str(error))
    finally:
        state["updated_utc"] = datetime.now(timezone.utc).isoformat()
        save()
        print("Pipeline status:", state["state"], flush=True)

if __name__ == "__main__":
    main()
