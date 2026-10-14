"""Recover feasible XOR/JE paths without losing independent branch entries."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image

ENTRY = 0x00401000


def test_recovery_skips_impossible_overlapping_call():
    code = bytes.fromhex("50 9c 31 c0 74 01 e8 9d 58 c3 90 90 90 90")
    image = synthetic_image({ENTRY: code})
    ins = image.recover(ENTRY, set(), bounds=(ENTRY, ENTRY + len(code)))
    assert not any(i.mnem == "CALL" for i in ins)
    assert {ENTRY + 7, ENTRY + 8, ENTRY + 9} <= {i.addr for i in ins}


def test_recovery_keeps_both_paths_from_independent_conditional_entry():
    code = bytes.fromhex("31 c0 74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")
    image = synthetic_image({ENTRY: code})
    ins = image.recover(ENTRY + 2, set(), bounds=(ENTRY, ENTRY + len(code)))
    assert {ENTRY + 4, ENTRY + 10} <= {i.addr for i in ins}


def test_unknown_incoming_edge_revisits_a_previously_constant_branch():
    # Initial JNE schedules the unknown-flags edge to the XOR/JE's JE.
    # Fallthrough first decodes XOR-self/JE and skips MOV EAX,2; the
    # previously pending independent edge must restore that MOV path.
    code = bytes.fromhex("75 02 31 c0 74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")
    image = synthetic_image({ENTRY: code})
    ins = image.recover(ENTRY, set(), bounds=(ENTRY, ENTRY + len(code)))
    assert {ENTRY + 6, ENTRY + 12} <= {i.addr for i in ins}


def test_known_branch_boundary_is_left_for_separate_unknown_flags_recovery():
    code = bytes.fromhex("31 c0 74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")
    image = synthetic_image({ENTRY: code})
    assert [i.mnem for i in image.recover(ENTRY, {ENTRY + 2})] == ["XOR"]


@pytest.mark.parametrize("prefix", [b"", b"\x66"])
def test_recovery_skips_impossible_jne_target(prefix):
    code = prefix + bytes.fromhex("31 c0 75 06 b8 01 00 00 00 c3 0f 0b c3")
    image = synthetic_image({ENTRY: code})
    ins = image.recover(ENTRY, set(), bounds=(ENTRY, ENTRY + len(code)))
    assert not any(i.mnem == "UD2" for i in ins)
