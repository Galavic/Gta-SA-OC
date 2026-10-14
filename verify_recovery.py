"""Check the cache patch against the pinned upstream decoder on original code."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import types

ROOT = Path(__file__).resolve().parent
KIT = ROOT / "vendor/recomp-kit"
PIN = "eb32cc42623e0e9e868b9d27423a57d5a5cba56b"


def load_pair():
    script = KIT / "tools/recomp/translate.py"
    original = subprocess.check_output(
        ["git", "-C", str(KIT), "show", PIN + ":tools/recomp/translate.py"], text=True, encoding="utf-8"
    )
    before = types.ModuleType("baseline_translate")
    before.__file__ = str(script)
    exec(compile(original, str(script), "exec"), before.__dict__)
    spec = importlib.util.spec_from_file_location("cached_translate", script)
    after = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(after)
    return before, after


def snapshot(insns):
    return [(i.addr, i.mnem, i.rep, tuple(i.ops), i.raw) for i in insns]


def recover_and_measure(module, image, function, addresses):
    insns = image.recover(function["address"], addresses - {function["address"]},
                          bounds=(function["address"], function["end"]))
    measured = module.Function(function["address"], "sample", function["size"], insns)
    measured.measure(image)
    return {
        "instructions": snapshot(insns), "end": measured.end,
        "contiguous": measured.contiguous, "fallthrough": measured.fallthrough,
    }


if __name__ == "__main__":
    before, after = load_pair()
    sample = json.loads((ROOT / "analysis/startup-probe.json").read_text())["functions"]
    addresses = {f["address"] for f in sample}
    a, b = before.Image(str(ROOT / "original/gta_sa.exe")), after.Image(str(ROOT / "original/gta_sa.exe"))
    expected = []
    started = time.perf_counter()
    for _ in range(3):
        values = [recover_and_measure(before, a, f, addresses) for f in sample]
        if not expected:
            expected = values
        else:
            assert values == expected
    baseline_seconds = time.perf_counter() - started
    started = time.perf_counter()
    for _ in range(3):
        values = [recover_and_measure(after, b, f, addresses) for f in sample]
        assert values == expected, "Cached recovery changed original instruction output"
    cached_seconds = time.perf_counter() - started
    report = {
        "compared_functions": len(sample), "nonempty_recoveries": sum(bool(x["instructions"]) for x in expected),
        "instructions_per_pass": sum(len(x["instructions"]) for x in expected), "passes": 3,
        "instruction_output_identical": True, "baseline_seconds": baseline_seconds,
        "function_boundaries_identical": True,
        "cached_seconds": cached_seconds, "cache": b._decode_recovery_instruction.cache_info()._asdict(),
        "instruction_end_cache": b._instruction_end_for_bytes.cache_info()._asdict(),
        "scope": "Recovery algorithm equivalence on bounded startup sample; not game execution",
    }
    (ROOT / "analysis/recovery-cache-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
