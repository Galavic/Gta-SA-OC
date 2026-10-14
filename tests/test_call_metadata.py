"""Nonlocal CALL contracts must stop only the audited call's fallthrough."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
from test_translate_insns import Opts
import translate as T


def test_one_call_contract_does_not_make_other_calls_to_that_callee_nonreturning():
    entry, ordinary, callee = 0x00401000, 0x00401020, 0x00401100
    image = synthetic_image({entry: bytes.fromhex("e8 fb 00 00 00 cc cc cc"), ordinary: bytes.fromhex("e8 db 00 00 00 c3"), callee: b"\xc3"})
    image.noreturn_sites = {entry}
    assert [i.mnem for i in image.recover(entry, set())] == ["CALL"]
    assert [i.mnem for i in image.recover(ordinary, set())] == ["CALL", "RET"]


def test_nonlocal_call_keeps_original_return_word_and_propagates_new_pc(monkeypatch):
    entry, callee = 0x00401000, 0x00401100
    image = synthetic_image({entry: bytes.fromhex("e8 fb 00 00 00"), callee: b"\xc3"})
    image.noreturn_sites = {entry}
    instructions = image.recover(entry, set())
    fn = T.Function(entry, "dispatcher_call", 5, instructions)
    fn.measure(image)
    monkeypatch.setattr(T, "RESUMABLE_STACKS", True)
    translator = T.Translator(image, {entry, callee}, Opts())
    translator.prepare(fn)
    text = "\n".join(translator.translate(fn))
    assert "wr32(c->r[4], 0x401005u);" in text
    assert "CALL_FN(00401100);" in text
    assert text.index("if (c->eip != 0x401005u) return;") < text.index("recomp_unmodelled(c, 0x401005u);")
    assert "fall-through past the listing" not in text


@pytest.mark.parametrize("alternate_jump_entry", [False, True])
def test_known_zero_jump_and_nonlocal_call_do_not_make_metadata_executable(alternate_jump_entry):
    entry, callee = 0x00401000, 0x00401100
    # JZ chooses a CALL or MOV ESP,0 / JMP ESP. DAA is exported metadata
    # following the audited CALL. A direct entry at JMP must retain it,
    # because its ESP would then be unknown rather than necessarily zero.
    code = bytes.fromhex("74 07 bc 00 00 00 00 ff e4 e8 f2 00 00 00 27 c3")
    image = synthetic_image({entry: code, callee: b"\xc3"})
    instructions = image.recover(entry, set())
    image.noreturn_sites = {entry+9}
    fn = T.Function(entry, "nonlocal_and_fixed_jump", len(code), instructions)
    fn.measure(image)
    known = {entry, callee} | ({entry+7} if alternate_jump_entry else set())
    translator = T.Translator(image, known, Opts())
    translator.prepare(fn)
    if alternate_jump_entry:
        with pytest.raises(T.TranslateError, match="DAA"):
            list(translator.translate(fn))
    else:
        text = "\n".join(translator.translate(fn))
        assert entry+14 in fn.dead_addrs
        assert "c->r[4] = 0x0u" in text
