"""A LOOP branch's taken path must be recovered alongside its fallthrough."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image


@pytest.mark.parametrize("opcode", [b"\xe0", b"\xe1", b"\xe2", b"\x67\xe0", b"\x67\xe1", b"\x67\xe2"])
def test_loop_recovery_keeps_both_original_paths(opcode):
    address = 0x00401000
    image = synthetic_image({address: opcode + b"\x06\xb8\x01\0\0\0\xc3\xb8\x02\0\0\0\xc3"})
    recovered = image.recover(address, set())
    taken = address + len(opcode) + 1 + 6
    assert taken in {i.addr for i in recovered}
    assert [i.mnem for i in recovered] == [recovered[0].mnem, "MOV", "RET", "MOV", "RET"]
