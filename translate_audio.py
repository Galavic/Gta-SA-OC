"""Run strict auxiliary DLL translations and retain each result separately."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parent


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    modules = cfg.get("modules", {}).get("aux", {})
    results = []
    env = dict(os.environ, PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    for key in modules:
        out = ROOT / "build/audio-probe" / key
        out.mkdir(parents=True, exist_ok=True)
        log = ROOT / "build" / f"audio-{key}-translate.log"
        command = [sys.executable, str(ROOT / "vendor/recomp-kit/tools/recomp/translate.py"), "--game", str(ROOT), "--module", key, "--out", str(out), "--report", str(ROOT / "build" / f"audio-{key}-report.json")]
        print(f"Translating original audio module {key}; log: {log}", flush=True)
        with log.open("w", encoding="utf-8") as output:
            result = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT)
        results.append(dict(module=key, exit_code=result.returncode, log=str(log), runtime_verified=False))
        print(f"{key}: exit {result.returncode}", flush=True)
        if result.returncode:
            print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]), flush=True)
    (ROOT / "build/audio-translation-status.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return int(any(r["exit_code"] for r in results))


if __name__ == "__main__":
    sys.exit(main())
