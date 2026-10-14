"""Guard unverified ENTER widths and its implicit register definitions."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
from test_translate_insns import Opts
import translate as T


@pytest.mark.parametrize("prefix", [b"\x66", b"\x66\x67"])
def test_unverified_16_bit_enter_is_rejected(prefix):
    entry = 0x00401000
    code = prefix + bytes.fromhex("c8 20 00 02 c3")
    image = synthetic_image({entry: code})
    instructions = image.recover(entry, set(), bounds=(entry, entry + len(code)))
    function = T.Function(entry, "unverified_enter", len(code), instructions)
    function.measure(image)
    translator = T.Translator(image, {entry}, Opts())
    translator.prepare(function)
    with pytest.raises(T.TranslateError, match="16-bit ENTER"):
        translator.translate(function)


def test_enter_invalidates_implicit_frame_and_stack_register_facts():
    instruction = synthetic_image({0x00401000: bytes.fromhex("c8 20 00 02 c3")}).recover(0x00401000, set())[0]
    assert T.Translator.writes_reg32(instruction, T.R_EBP)
    assert T.Translator.writes_reg32(instruction, T.R_ESP)
    assert not T.Translator.writes_reg32(instruction, T.R_EAX)
