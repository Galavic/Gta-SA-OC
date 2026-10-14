"""Original bytes must confirm Ghidra's branch prediction annotation."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
from test_translate_insns import Opts
import translate as T

ENTRY = 0x401000


def emit(prefix, annotation, mnemonic="JA", target=ENTRY+3):
    image = synthetic_image({ENTRY: bytes([prefix, 0x77, 0, 0xc3])})
    instructions = T.parse_listing_text(
        f"{ENTRY:08x}  {mnemonic} {target:#x}, {annotation}\n{ENTRY+3:08x}  RET\n")
    fn = T.Function(ENTRY, "hinted", 4, instructions)
    fn.measure(image)
    translator = T.Translator(image, {ENTRY}, Opts())
    translator.prepare(fn)
    return "\n".join(translator.translate(fn))


@pytest.mark.parametrize("prefix,annotation", [(0x2e, "bn"), (0x3e, "bt")])
def test_original_conditional_hint_preserves_branch_condition(prefix, annotation):
    text = emit(prefix, annotation)
    assert "eflags_cf" in text and "eflags_zf" in text
    assert "unmodelled" not in text


@pytest.mark.parametrize("prefix,annotation,mnemonic,target", [
    (0x3e, "bn", "JA", ENTRY+3),
    (0x2e, "bn", "JBE", ENTRY+3),
    (0x2e, "bn", "JA", ENTRY+4),
])
def test_contradicting_listing_hint_cannot_override_original_branch(prefix, annotation, mnemonic, target):
    with pytest.raises(T.TranslateError, match="unverified branch prediction"):
        emit(prefix, annotation, mnemonic, target)
