"""Normalize the exact /6 encodings measured by the native Windows oracle."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
import translate as T


@pytest.mark.parametrize("sal,shl,operands", [
    ("d3f5", "d3e5", ["EBP", "CL"]),
    ("c1f506", "c1e506", ["EBP", "0x6"]),
])
def test_original_dispatcher_shift_forms_share_canonical_flag_model(sal, shl, operands):
    decoded = []
    for machine in (sal, shl):
        image = synthetic_image({0x401000: bytes.fromhex(machine)+b"\xc3"})
        instructions = image.recover(0x401000, set())
        decoded.append((instructions[0].mnem, instructions[0].ops))
    assert decoded == [("SHL", operands), ("SHL", operands)]
    listing = T.parse_listing_text("00401000  SAL " + ",".join(operands))
    assert listing[0].mnem == "SHL"
    assert listing[0].ops == operands
    assert listing[0].raw.startswith("00401000  SAL")
