"""Recovery must keep the same CFG when stop exclusions are borrowed."""
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
import translate as T


def signature(insns):
    return [(i.addr, i.mnem, i.rep, i.ops, i.raw) for i in insns]


def test_nested_stop_exclusions_match_materialized_membership():
    rng = random.Random(71)
    stops = set(rng.sample(range(10000), 3000))
    first = set(rng.sample(range(10000), 600))
    second = set(rng.sample(range(10000), 700))
    view = T.RecoveryStopsWithout(T.RecoveryStopsWithout(stops, first), second)
    reference = (stops - first) - second
    first.clear()
    second.add(10001)
    assert {address for address in range(10002) if address in view} == reference


def test_recovery_cfg_and_error_state_match_reference_across_exclusions():
    start = 0x401000
    # CMP/JNE creates two paths sharing the final RET; excludes can expose
    # either path, and an independent boundary can still stop recovery.
    image = synthetic_image({start: bytes.fromhex("83 f8 01 75 03 90 eb 01 90 c3")})
    instructions = {start, start + 3, start + 5, start + 6, start + 8, start + 9}
    for mask in range(64):
        excluded = {a for bit, a in enumerate(sorted(instructions)) if mask & (1 << bit)}
        for boundaries in ((), (start + 8,)):
            reference = image.recover(start, instructions - excluded, boundaries=boundaries)
            previous_errors = list(image.recover_errors)
            borrowed = image.recover(start, T.RecoveryStopsWithout(instructions, excluded), boundaries=boundaries)
            assert signature(borrowed) == signature(reference)
            assert image.recover_errors == previous_errors


def test_fresh_views_use_updated_stop_ownership():
    stops = {1, 2}
    assert 3 not in T.RecoveryStopsWithout(stops, {1})
    stops.add(3)
    # A new recovery operation sees changed ownership; there is no stale
    # memoized difference keyed only by the stop-set identity.
    assert 3 in T.RecoveryStopsWithout(stops, {1})
    assert 1 not in T.RecoveryStopsWithout(stops, {1})
