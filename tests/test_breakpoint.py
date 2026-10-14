"""Breakpoint opcodes must use the runtime's stop, not its ignored interrupt."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
from test_translate_insns import Opts
import translate as T


@pytest.mark.parametrize("opcode", ["cc", "cd03"])
def test_original_breakpoint_uses_the_fatal_runtime_handler(opcode):
    entry = 0x00401000
    image = synthetic_image({entry: bytes.fromhex(opcode + "c3")})
    image.md.detail = True
    decoded = next(image.md.disasm(bytes.fromhex(opcode), entry))
    instruction = image.to_insn(decoded)
    image.md.detail = False
    function = T.Function(entry, "breakpoint", len(bytes.fromhex(opcode)), [instruction])
    function.measure(image)
    tr = T.Translator(image, {entry}, Opts())
    tr.prepare(function)
    emitted = "\n".join(tr.translate(function))
    assert "recomp_breakpoint(c, 0x401000u); return;" in emitted
    assert "recomp_int" not in emitted
