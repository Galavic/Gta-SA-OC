"""Recovery must respect audited data on every kind of incoming path."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image

ENTRY = 0x00401000


@pytest.mark.parametrize("bounded", [False, True])
def test_recovery_stops_before_data_on_fallthrough(bounded):
    image = synthetic_image({ENTRY: bytes.fromhex("90 90 c3")})
    image.declare_data_regions([(ENTRY + 1, ENTRY + 2)])
    bounds = (ENTRY, ENTRY + 3) if bounded else None
    assert [i.addr for i in image.recover(ENTRY, set(), bounds=bounds)] == [ENTRY]
    assert image.recover(ENTRY + 1, set(), bounds=bounds) == []


def test_jump_over_data_recovers_original_destination():
    image = synthetic_image({ENTRY: bytes.fromhex("eb 02 cc cc c3")})
    image.declare_data_regions([(ENTRY + 2, ENTRY + 4)])
    assert {i.addr for i in image.recover(ENTRY, set())} == {ENTRY, ENTRY + 4}


def test_branch_into_data_does_not_decode_it():
    image = synthetic_image({ENTRY: bytes.fromhex("75 01 c3 c3")})
    image.declare_data_regions([(ENTRY + 3, ENTRY + 4)])
    assert {i.addr for i in image.recover(ENTRY, set())} == {ENTRY, ENTRY + 2}
