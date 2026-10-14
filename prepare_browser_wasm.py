"""Reduce diagnostic Wasm locals and validate with V8 before publishing.

This changes compiler temporaries only, retaining all game functions and data.
The original linked binary is kept beside the browser artifact for comparison.
"""
import argparse
import json
import mmap
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def uleb(data, offset):
    value = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if not byte & 128:
            return value, offset
        shift += 7
        if shift > 63:
            raise ValueError("Invalid Wasm LEB128")


def inspect_and_strip(source, destination=None):
    """Count locals, stripping custom debug sections without decoding instructions."""
    high = []
    maximum = functions = 0
    output = destination.open("wb") if destination else None
    try:
        with source.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            assert data[:8] == b"\0asm\1\0\0\0"
            if output:
                output.write(data[:8])
            cursor = 8
            while cursor < len(data):
                start = cursor
                section = data[cursor]
                size, payload = uleb(data, cursor + 1)
                end = payload + size
                assert end <= len(data)
                if section == 10:
                    count, position = uleb(data, payload)
                    functions = count
                    for index in range(count):
                        body_size, body = uleb(data, position)
                        position = body + body_size
                        groups, local = uleb(data, body)
                        total = 0
                        for _ in range(groups):
                            number, local = uleb(data, local)
                            total += number
                            local += 1  # This build uses numeric/reference shorthand types.
                        maximum = max(maximum, total)
                        if total >= 50000:
                            high.append(dict(defined_index=index, locals=total))
                keep = True
                if section == 0:
                    length, name_start = uleb(data, payload)
                    name = data[name_start:name_start + length]
                    keep = not name.startswith(b".debug_")
                if output and keep:
                    for part in range(start, end, 1024 * 1024):
                        output.write(data[part:min(part + 1024 * 1024, end)])
                cursor = end
    finally:
        if output:
            output.close()
    return dict(functions=functions, maximum_locals=maximum, excessive_locals=high)


def prepare(sdk):
    started = time.time()
    directory = ROOT / "build/web/recomp"
    source = directory / "GTASARecomp.wasm"
    original = directory / "GTASARecomp.linked.wasm"
    stripped = directory / "GTASARecomp.stripped.wasm"
    candidate = directory / "GTASARecomp.browser.wasm"
    status_file = ROOT / "build/browser-wasm-status.json"
    status = dict(state="running", pid=os.getpid(), playable_verified=False)
    def save():
        status_file.write_text(json.dumps(status, indent=2), encoding="utf-8")
    save()
    try:
        if not original.exists():
            shutil.copy2(source, original)
        status["before"] = inspect_and_strip(source, stripped)
        save()
        print("Before:", status["before"], flush=True)
        # Limit parallel scratch graphs on this machine while keeping two cores busy.
        env = dict(os.environ, BINARYEN_CORES="2")
        command = [str(sdk / "upstream/bin/wasm-opt.exe"), str(stripped),
                   "--all-features", "--coalesce-locals", "--vacuum", "--strip-debug",
                   "-o", str(candidate)]
        if status["before"]["excessive_locals"]:
            subprocess.run(command, env=env, check=True)
        else:
            shutil.copy2(stripped, candidate)
        status["after"] = inspect_and_strip(candidate)
        print("After:", status["after"], flush=True)
        assert status["after"]["functions"] == status["before"]["functions"]
        assert not status["after"]["excessive_locals"], "Wasm still exceeds browser local limits"
        node = next((sdk / "node").glob("*/node.exe"))
        # Compiling the entire module checks browser-engine limits, beyond binary validity.
        check = "const fs=require('fs'); WebAssembly.compile(fs.readFileSync(process.argv[1])).then(()=>console.log('V8 full module compilation passed')).catch(e=>{console.error(e);process.exit(1)});"
        subprocess.run([str(node), "-e", check, str(candidate)], check=True)
        status["v8_compile_passed"] = True
        shutil.copy2(candidate, source)
        site = ROOT / "build/web-site/gtasa/GTASARecomp.wasm"
        pending = site.with_suffix(".wasm.new")
        shutil.copy2(candidate, pending)
        pending.replace(site)
        status.update(state="finished", exit_code=0, bytes=candidate.stat().st_size,
                      seconds=time.time() - started)
    except Exception as error:
        status.update(state="failed", error=str(error), exit_code=1, seconds=time.time() - started)
        raise
    finally:
        save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--emsdk", type=Path, default=Path.home() / "GTASAWebToolchains/emsdk")
    args = parser.parse_args()
    if args.background:
        with (ROOT / "build/browser-wasm.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                        "--emsdk", str(args.emsdk)], cwd=ROOT,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
        print("Browser Wasm preparation PID", process.pid)
    else:
        prepare(args.emsdk)
