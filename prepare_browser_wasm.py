"""Optimise the linked Wasm and validate it with V8 before publishing.

The link rule compiles the recompiled C with -pthread -g and no -O, so the
module reaches the browser as unoptimised code.  wasm-opt -O2 reduces it and
rewrites it: locals drop far below the browser limit, and functions are inlined
and dropped, so the function count legitimately falls.  Game data and behaviour
are unchanged; only code shape is.  Measured on this game, 249.3 MB -> 224.8 MB
and 4.55 -> 3.40-3.70 ns per guest instruction, with no recompilation.

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
import tomllib

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


def prepare(sdk, game_dir=ROOT):
    started = time.time()
    game_dir = Path(game_dir).resolve()
    config = tomllib.loads((game_dir / "game.toml").read_text(encoding="utf-8"))["game"]
    app_name, game_id = config["app_name"], config["id"]
    directory = game_dir / "build/web/recomp"
    source = directory / f"{app_name}.wasm"
    original = directory / f"{app_name}.linked.wasm"
    stripped = directory / f"{app_name}.stripped.wasm"
    candidate = directory / f"{app_name}.browser.wasm"
    status_file = game_dir / "build/browser-wasm-status.json"
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
        # -O2 always, not only when a function exceeds the local limit.  The link
        # rule compiles the recompiled C with -pthread -g and no -O, so without
        # this pass the module reaches the browser as unoptimised code.  Measured
        # on this game: 249.3 MB -> 224.8 MB and 4.55 -> 3.40-3.70 ns per guest
        # instruction, i.e. ~22% more instructions per second for one post-link
        # pass and no recompilation.  It costs roughly 800-1300 s, which is why
        # it lives here and not in the build.
        #
        # No --all-features.  It makes wasm-opt validate and emit against every
        # proposal, and on this module the result fails V8 with "unknown import
        # kind 0x7f" even though wasm-opt's own validator accepts it.  The
        # features this module actually uses are on by default in this binaryen,
        # and the V8 compile below is what proves it.
        command = [str(sdk / "upstream/bin/wasm-opt.exe"), str(stripped),
                   "-O2", "--strip-debug", "-o", str(candidate)]
        subprocess.run(command, env=env, check=True)
        status["after"] = inspect_and_strip(candidate)
        print("After:", status["after"], flush=True)
        # -O2 inlines and drops functions, so the count is expected to fall and
        # asserting equality would reject every optimised module.  What must not
        # happen is an empty or larger module: that would mean the optimiser was
        # handed the wrong input.
        assert 0 < status["after"]["functions"] <= status["before"]["functions"], (
            "wasm-opt produced %d functions from %d"
            % (status["after"]["functions"], status["before"]["functions"]))
        assert not status["after"]["excessive_locals"], "Wasm still exceeds browser local limits"
        node = next((sdk / "node").glob("*/node.exe"))
        # Compiling the entire module checks browser-engine limits, beyond binary validity.
        check = "const fs=require('fs'); WebAssembly.compile(fs.readFileSync(process.argv[1])).then(()=>console.log('V8 full module compilation passed')).catch(e=>{console.error(e);process.exit(1)});"
        subprocess.run([str(node), "-e", check, str(candidate)], check=True)
        status["v8_compile_passed"] = True
        shutil.copy2(candidate, source)
        site = game_dir / "build/web-site" / game_id / f"{app_name}.wasm"
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
    parser.add_argument("--game-dir", type=Path, default=ROOT,
                        help="Game directory whose build/web/recomp to prepare (default: repository root)")
    args = parser.parse_args()
    if args.background:
        game_dir = args.game_dir.resolve()
        log_path = game_dir / "build/browser-wasm.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                        "--emsdk", str(args.emsdk), "--game-dir", str(game_dir)],
                                       cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
        print("Browser Wasm preparation PID", process.pid)
    else:
        prepare(args.emsdk, args.game_dir)
