"""Benchmark identical withdrawn-dispatch rewrites on emitted GTA bodies."""
from pathlib import Path
import json
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def materialized_reference(body, pruned):
    if not pruned:
        return body
    out = []
    for line in body:
        def call(m):
            target = int(m.group(1), 16)
            return m.group(0) if target not in pruned else "recomp_unknown_call(c, 0x%08xu); return;" % target

        def jump(m):
            target = int(m.group(1), 16)
            return m.group(0) if target not in pruned else "recomp_unknown_call(c, 0x%08xu); return;" % target
        out.append(T.WITHDRAWN_JUMP_RE.sub(jump, T.WITHDRAWN_CALL_RE.sub(call, line)))
    return out


def main():
    source = ROOT / "build/wide-latest-function-probe"
    paths = sorted(source.glob("*.c"))
    assert paths, "Expected emitted original GTA probe bodies"
    bodies = [p.read_text(encoding="utf-8").splitlines() for p in paths]
    # Remove alternating actual transfers, preserving both retained and
    # withdrawn rewrites without depending on one full-build prune outcome.
    targets = sorted({int(m.group(1), 16) for body in bodies for line in body for pattern in (T.WITHDRAWN_CALL_RE, T.WITHDRAWN_JUMP_RE) for m in pattern.finditer(line)})
    pruned = set(targets[::2])
    assert pruned
    timings = {"reference": [], "guarded": []}
    runs = {"reference": materialized_reference, "guarded": T.retarget_withdrawn}
    for pass_index in range(5):
        for mode in (("reference", "guarded") if pass_index % 2 == 0 else ("guarded", "reference")):
            start = time.perf_counter()
            for _ in range(20):
                result = [runs[mode](body, pruned) for body in bodies]
            timings[mode].append(time.perf_counter() - start)
            if mode == "reference":
                reference = result
            else:
                assert result == reference
    medians = {key: statistics.median(value) for key, value in timings.items()}
    report = {"emitted_original_bodies": len(bodies), "emitted_lines": sum(map(len, bodies)), "passes": 5, "iterations_per_pass": 20,
              "rewrite_outputs_equal": True, "timings_seconds": timings, "median_seconds": medians,
              "sample_speedup": medians["reference"] / medians["guarded"],
              "scope": "Withdrawn transfer rewrite only; sampled prune addresses, not full build or game runtime."}
    (ROOT / "build/perf-retarget-withdrawn.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
