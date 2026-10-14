"""Run original CPU entry in Node with a null host; never gameplay verification."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parent


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return dict(path=str(path), sha256=digest.hexdigest(), size=path.stat().st_size)


def crt_startup_info_milestone(stderr):
    """Observe actual adapter entry/return at the byte-verified CRT callsite.

    The original call at 00825486 returns to 0082548c. This adapter return
    precedes the eventual WinMain call; it does not prove that call executed.
    """
    name = r"kernel32\.dll!GetStartupInfoA"
    incoming = re.search(r"-> " + name + r" \(esp=[0-9a-f]{8} ret=0082548c\)", stderr, re.I)
    outgoing = re.search(r"<- " + name + r" \(eax=[0-9a-f]{8}\)",
                         stderr[incoming.end():] if incoming else "", re.I)
    return dict(original_crt_callsite="00825486", return_address="0082548c",
                import_name="KERNEL32.dll!GetStartupInfoA",
                adapter_entry_observed=bool(incoming), adapter_return_observed=bool(outgoing),
                winmain_execution_verified=False, menu_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build/boot-probe-runs",
                        help="Parent output directory; every execution creates a fresh run directory")
    parser.add_argument("--timeout", type=float, default=60,
                        help="Maximum runtime in seconds, from 1 through 60")
    parser.add_argument("--trace-imports", action="store_true",
                        help="Record existing native LOGV import call/return traces locally")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be from 1 through 60 seconds")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:8]
    folder = args.out.resolve() / run_id
    folder.mkdir(parents=True, exist_ok=False)
    node = next((Path.home() / "GTASAWebToolchains/emsdk/node").glob("*/node.exe"))
    probe = ROOT / "build/web/recomp/game_boot_probe.js"
    wasm = probe.with_suffix(".wasm")
    exe = ROOT / "prepared/gta_sa.exe"
    provenance = dict(probe_javascript=fingerprint(probe), probe_wasm=fingerprint(wasm),
                      executable=fingerprint(exe), game_config=fingerprint(ROOT / "game.toml"))
    env = dict(os.environ)
    env["RECOMP_PROBE_DUMP"] = str(folder / "halt")
    env["RECOMP_PROFILE_DIR"] = str(folder / "profile")
    if args.trace_imports:
        env["RECOMP_LOG"] = "2"
    command = [str(node), str(probe), str(exe)]
    timed_out = False
    started = time.monotonic()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    error = None
    code = None
    with (folder / "stdout.log").open("w", encoding="utf-8") as out, \
            (folder / "stderr.log").open("w", encoding="utf-8") as err:
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=err,
                                       creationflags=flags)
            try:
                code = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                code = process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = str(exc)
    stderr = (folder / "stderr.log").read_text(encoding="utf-8", errors="replace")
    targets = re.findall(r"(?:unknown target|untranslated code at|interpreter failed at) ([0-9a-fA-F]{8})", stderr)
    targets.extend(re.findall(r"no block entry for indirect jump to 0x([0-9a-fA-F]{8})", stderr))
    diagnostic_lines = [line for line in stderr.splitlines()
                        if any(word in line for word in ("refusing", "decoder:", "interpreter failed",
                                                         "strict imports:", "[boot-probe] loader:", "Aborted(",
                                                         "no block entry for indirect jump"))]
    manifest = folder / "halt.json"
    snapshot = None
    if manifest.exists():
        try:
            snapshot = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            error = "Invalid snapshot manifest: " + str(exc)
    native_errors = [line for line in diagnostic_lines
                     if "[recomp]" in line or "[boot-probe]" in line or line.startswith("recomp:")]
    meaningful_error = native_errors[-1] if native_errors else (diagnostic_lines[-1] if diagnostic_lines else error)
    snapshot_target = snapshot.get("target") if snapshot else None
    last_target = f"{snapshot_target:08x}" if isinstance(snapshot_target, int) else (targets[-1].lower() if targets else None)
    status = dict(run_id=run_id, output_directory=str(folder), exit_code=code,
                  timeout=timed_out, timeout_seconds=args.timeout,
                  elapsed_seconds=round(time.monotonic() - started, 3),
                  original_entry="[boot-probe] original entry begins;" in stderr,
                  strict_unknown=True, strict_imports=True, null_host=True,
                  trace_imports=args.trace_imports,
                  crt_startup_info=crt_startup_info_milestone(stderr),
                  gameplay_verified=False, browser_execution_verified=False,
                  last_target=last_target,
                  last_error=meaningful_error[:4000] if meaningful_error else None,
                  runner_error=error, snapshot_manifest_exists=manifest.exists(),
                  snapshot_complete=bool(snapshot and all(r.get("written") for r in snapshot.get("regions", []))),
                  provenance=provenance)
    (folder / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    pointer = ROOT / "build/boot-probe-last-run.json"
    temporary = pointer.with_name("boot-probe-last-run." + run_id + ".tmp")
    temporary.write_text(json.dumps(dict(run_id=run_id, status_file=str(folder / "status.json")),
                                    indent=2), encoding="utf-8")
    os.replace(temporary, pointer)
    print(json.dumps(status, indent=2))
    for line in stderr.splitlines():
        if "[recomp]" in line or "[boot-probe]" in line:
            print(line[:4000])


if __name__ == "__main__":
    main()
