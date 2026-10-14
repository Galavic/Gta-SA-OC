"""Fast prefix guards must preserve every legacy regex rewrite."""
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from perf_retarget_withdrawn import materialized_reference
import translate as T


def test_guarded_transfer_rewrite_matches_legacy_patterns():
    rng = random.Random(144)
    forms = ["CALL_FN({:08x});", "CALL_FN({:08x}); return;", "recomp_jump(c, 0x{:x}u); return;",
             "c->eip = 0x11111u; recomp_jump(c, 0x{:x}u); return;", "CALL_FN({:08X});", "recomp_jump(c, 0x{:x}); return;",
             "/* CALL_FN({:08x}); */", "// recomp_jump(c, 0x{:x}u); return;"]
    addresses = [0, 1, 0x400001, 0x12345678, 0xffffffff]
    lines = ["c->r[0] += 1;", "", "CALL_FN(garbage);", "recomp_jump(c, target); return;"]
    for _ in range(500):
        lines.append(" ".join(rng.choice(forms).format(rng.choice(addresses)) for _ in range(rng.randrange(1, 5))))
    for pruned in (set(), {0, 0x400001, 0xffffffff}, set(addresses)):
        assert T.retarget_withdrawn(lines, pruned) == materialized_reference(lines, pruned)


def test_empty_prune_set_preserves_body_identity():
    body = ["CALL_FN(00400001); return;"]
    assert T.retarget_withdrawn(body, set()) is body
