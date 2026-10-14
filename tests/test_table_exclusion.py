"""Indexed table storage exclusions preserve source/target boundaries."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image


@pytest.mark.parametrize("kind", ["target", "source"])
@pytest.mark.parametrize("offset", [-1, 0, 1, 2, 3])
def test_indexed_exclusion_union_has_exclusive_upper_boundary(kind, offset):
    target, holder = 0x00402370, 0x00401800
    image = synthetic_image({target - 1: b"\x90\x8b\x44\x24\x04\xc3",
                             holder: target.to_bytes(4, "little")}, size=0x4000)
    candidate = target if kind == "target" else holder
    lo = candidate - offset
    # Unsorted, overlapping, adjacent and empty intervals. The union is
    # exactly [lo, lo+3); unrelated ranges must not alter its boundaries.
    ranges = [(lo + 1, lo + 2), (lo + 2, lo + 3), (lo, lo + 2), (lo, lo)]
    ranges += [(0x00403000 + i * 4, 0x00403002 + i * 4) for i in range(128)]
    expected = any(a <= candidate < b for a, b in ranges)
    starts, _ = image.code_pointers(set(), exclude=ranges)
    assert (target in starts) == (not expected)
    # Existing instruction boundaries retain their original priority over
    # excluded storage; indexing must not reorder these tests.
    _, interior = image.code_pointers({target}, exclude=ranges)
    assert target in interior
