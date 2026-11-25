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
        # The four audio DLLs: keep a translation made by the current translator,
        # translate again otherwise. Never the old game's code.
        current = tomllib.loads((VARIANT / "game.toml").read_text(encoding="utf-8"))
        reused = []
        for key, module in current["modules"]["aux"].items():
            assert hashlib.sha256((VARIANT / module["path"]).read_bytes()).hexdigest() == module["sha256"]
            # The DLL is translated by the same translator as the image: a module
            # translation older than the image's came from an earlier translator
            # and may call runtime symbols that no longer exist, so it is redone.
            own_report = VARIANT / f"build/recomp/translate-{key}-report.json"
            own_source = VARIANT / f"build/recomp/gen/aux-{key}"
            image_report = VARIANT / "build/recomp/translate-report.json"
            fresh = (own_report.is_file() and (own_source / "table.c").is_file() and
                     own_report.stat().st_mtime >= image_report.stat().st_mtime)
            if not fresh:
                stage = VARIANT / f"build/recomp/aux-stage-{key}"
                shutil.rmtree(stage, ignore_errors=True)
                (stage / f"aux-{key}").mkdir(parents=True)
                subprocess.run([sys.executable, str(ROOT / "vendor/recomp-kit/tools/recomp/translate.py"),
                                "--out", str(stage / f"aux-{key}"), "--game", str(VARIANT),
                                "--module", key, "--report", str(stage / "report.json")],
                               cwd=ROOT / "vendor/recomp-kit", check=True)
                shutil.rmtree(own_source, ignore_errors=True)
                shutil.move(str(stage / f"aux-{key}"), str(own_source))
                shutil.move(str(stage / "report.json"), str(own_report))
                shutil.rmtree(stage)
            audio = json.loads(own_report.read_text())
            assert not audio["failures"] and not audio["unmodelled"]
            assert not audio["table_gaps"] and not audio["table_sites_undecoded"]
            assert (own_source / "table.c").is_file()
            reused.append(key)
        state.update(state="building_wasm", reused_audio_modules=reused)
        save()
        sdk = Path.home() / "GTASAWebToolchains/emsdk"
        assert (sdk / ".emscripten").is_file()
        env = dict(os.environ, EMSDK=str(sdk), EM_CONFIG=str(sdk / ".emscripten"), PYTHONUTF8="1")
        env["PATH"] = os.pathsep.join([str(ROOT / ".venv/Scripts"),
                                       str(sdk / "upstream/emscripten"), env.get("PATH", "")])
        # Normal -O2 for the generated chunks. --diagnostic-all compiles every
        # chunk with the LLVM optimizer disabled: it builds faster but measured
        # 19.8 against 37.9 city FPS (docs/STATUS.md, 2026-11-25).
        command = [sys.executable, "-u", str(ROOT / "vendor/recomp-kit/tools/build.py"),
                   "--game-dir", str(VARIANT), "--target", "web", "--jobs", "6"]
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
