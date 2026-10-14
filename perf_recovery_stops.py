"""Compare materialized and membership-only stops on original GTA CFGs."""
from pathlib import Path
import hashlib
import json
import statistics
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def signature(insns):
    return [(i.addr, i.mnem, i.rep, i.ops, i.raw) for i in insns]


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    binary = ROOT / cfg["game"]["developer_exe"]
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    assert digest == cfg["game"]["sha256"]
    image = T.Image(str(binary))
    stops = set()
    bodies = []
    for path in sorted((ROOT / cfg["translate"]["listings"] / "functions").glob("*.asm")):
        addresses = [int(line.split()[0], 16) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        stops.update(addresses)
        if len(addresses) >= 8:
            bodies.append(addresses)
    cases = [bodies[i * len(bodies) // 64] for i in range(64)]
    timings = {"materialized": [], "borrowed": []}
    outputs = {}
    for run in range(3):
        for mode in (("materialized", "borrowed") if run % 2 == 0 else ("borrowed", "materialized")):
            result = []
            before = time.perf_counter()
            for addresses in cases:
                excluded = set(addresses)
                blocked = set(stops) - excluded if mode == "materialized" else T.RecoveryStopsWithout(stops, excluded)
                result.append(signature(image.recover(addresses[0], blocked)))
            timings[mode].append(time.perf_counter() - before)
            outputs[mode] = result
    assert outputs["materialized"] == outputs["borrowed"]
    medians = {key: statistics.median(value) for key, value in timings.items()}
    report = {"original_sha256": digest, "ownership_instruction_count": len(stops), "original_function_cases": len(cases), "passes": 3,
              "recovery_outputs_equal": True, "timings_seconds": timings, "median_seconds": medians,
              "sample_speedup": medians["materialized"] / medians["borrowed"],
              "scope": "Stop exclusion construction plus original CFG recovery; not full translation or game runtime."}
    target = ROOT / "build/perf-recovery-stops.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
