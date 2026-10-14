"""Audit the user's PE and lift a bounded startup sample, without executing it.

Generated guest code stays in ignored build/. This is a translation probe,
not a runnable game, and its output uses pcrecomp's runtime, not recomp-kit's.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PIN = "cd885d84bcbdacddc27bdbd6676e376557f118f090e71e0db7c746e72c949064"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("--max-functions", type=int, default=64)
    args = parser.parse_args()
    data = args.exe.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != PIN:
        parser.error(f"Executable differs from audited version: {digest}")
    if not 1 <= args.max_functions <= 1024:
        parser.error("--max-functions must be between 1 and 1024")
    toolkit = ROOT / "vendor/pcrecomp"
    for folder in ("pe", "disasm", "lift"):
        sys.path.insert(0, str(toolkit / "tools" / folder))
    from pe_analyze import analyze_pe, build_iat_map, export_json
    from disasm32 import Disassembler, _func_to_dict
    from lift32 import Lifter

    analysis = ROOT / "analysis"
    generated = ROOT / "build/startup-probe"
    analysis.mkdir(exist_ok=True)
    generated.mkdir(parents=True, exist_ok=True)
    info = analyze_pe(str(args.exe), do_hashes=True)
    export_json(info, str(analysis / "pe.json"))
    iat = build_iat_map(info)
    dis = Disassembler(data, info.image_base, info.sections)
    entry = info.image_base + info.entry_point_rva
    queue, visited, functions, rejected = deque([entry]), set(), {}, []
    # Only traverse direct code calls. Dynamic calls, DLLs, and jump tables
    # remain unproven; this must never be presented as complete discovery.
    while queue and len(functions) < args.max_functions:
        address = queue.popleft()
        if address in visited or address in iat:
            continue
        visited.add(address)
        if dis._va_to_offset(address) is None:
            rejected.append(hex(address))
            continue
        function = dis.disassemble_function(address, iat)
        if function is None:
            rejected.append(hex(address))
            continue
        functions[address] = function
        queue.extend(sorted(function.calls_to))
    if entry not in functions:
        raise RuntimeError("Entry point could not be decoded; no startup translation produced")
    lifter = Lifter(iat_map=iat, lifted=set(functions))
    sources = []
    for address, function in sorted(functions.items()):
        source = lifter.lift_function(function)
        (generated / f"fn_{address:08x}.c").write_text(source, encoding="utf-8")
        sources.append(source)
    section_result = subprocess.run(
        [sys.executable, str(toolkit / "tools/pe/analyze_sections.py"), str(args.exe)],
        capture_output=True, text=True, check=True,
    )
    (analysis / "sections.txt").write_text(section_result.stdout, encoding="utf-8")
    commits = {}
    for name in ("pcrecomp", "recomp-kit"):
        commits[name] = subprocess.check_output(
            ["git", "-C", str(ROOT / "vendor" / name), "rev-parse", "HEAD"], text=True
        ).strip()
    joined = "\n".join(sources)
    report = {
        "sha256": digest, "file_size": len(data), "entry_point": hex(entry),
        "toolkit_commits": commits, "sample_functions": len(functions),
        "sample_instructions": sum(f.num_instructions for f in functions.values()),
        "unvisited_direct_targets": len(set(queue) - visited),
        "rejected_targets": rejected,
        "todo_markers": joined.count("TODO"),
        "runtime_dispatch_sites": joined.count("RECOMP_ICALL"),
        "compiled": False, "wasm_generated": False, "playable": False,
        "limitations": [
            "Bounded static startup sample; not complete function recovery",
            "Generated C uses pcrecomp; recomp-kit requires its own translation",
            "No instruction equivalence tests, compilation, or browser execution yet",
            "Win32, D3D9, audio and dynamic DLL compatibility remain unverified",
        ],
        "functions": [_func_to_dict(f) for f in functions.values()],
    }
    (analysis / "startup-probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Translated sample: {len(functions)} functions, {report['sample_instructions']} instructions")
    print(f"TODO markers: {report['todo_markers']}; runtime dispatch sites: {report['runtime_dispatch_sites']}")
    print("No executable or Wasm game has been built.")


if __name__ == "__main__":
    main()
