"""An opaque branch is constant only when no alternate path enters the JE."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
from test_translate_insns import Opts
import translate as T

ENTRY = 0x00401000
# XOR EAX,EAX; JE +5; CALL far outside image; RET.
CODE = bytes.fromhex("31 c0 74 05 e8 11 22 33 44 c3")


def listed_instruction(fields):
    address, mnemonic, rep, operands, raw = fields
    return T.Insn(address, mnemonic, rep, list(operands), raw)


def translate(code=CODE, entries=(), known=(), listing_image=None):
    image = synthetic_image({ENTRY: code})
    source = listing_image or image
    source.md.detail = True
    instructions = [listed_instruction(source._decode_recovery_instruction(i.address, source.data).fields)
                    for i in source.md.disasm(source.data[ENTRY-source.base:ENTRY-source.base+len(code)], ENTRY)]
    source.md.detail = False
    fn = T.Function(ENTRY, "constant_branch", len(code), instructions)
    fn.measure(image)
    translator = T.Translator(image, {ENTRY} | set(known), Opts())
    translator.prepare(fn)
    return fn, "\n".join(translator.translate(fn, entries))


def test_impossible_original_call_is_removed_and_xor_kept():
    fn, text = translate()
    assert fn.proven_zero_branches == {1: True}
    assert fn.dead_addrs == {ENTRY + 4}
    assert "CALL" not in text
    assert "XOR EAX,EAX" in text
    assert "c->eflags_zf" in text
    assert "if (c->eflags_zf)" not in text


@pytest.mark.parametrize("entry_kind", ["alternate", "known"])
def test_independent_entry_into_branch_keeps_both_original_paths(entry_kind):
    branch = ENTRY + 2
    fn, text = translate(entries=(branch,) if entry_kind == "alternate" else (),
                         known=(branch,) if entry_kind == "known" else ())
    assert not fn.proven_zero_branches
    assert not fn.dead_addrs
    assert "if (c->eflags_zf)" in text
    assert "CALL" in text


def test_computed_jump_disables_single_entry_proof():
    fn, text = translate(CODE[:-1] + bytes.fromhex("ff e2"))
    assert not fn.proven_zero_branches
    assert "CALL" in text


def test_a_listing_that_disagrees_with_original_xor_cannot_prove_the_branch():
    listed = synthetic_image({ENTRY: CODE})
    fn, text = translate(bytes.fromhex("31 d0") + CODE[2:], listing_image=listed)
    assert not fn.proven_zero_branches
    assert "CALL" in text


def test_a_direct_path_into_the_branch_keeps_it_conditional():
    # Same XOR/JE with an independently entered tail that jumps to JE.
    code = CODE + bytes.fromhex("eb f6")
    image = synthetic_image({ENTRY: code})
    image.md.detail = True
    ins = [listed_instruction(image._decode_recovery_instruction(i.address, image.data).fields)
           for i in image.md.disasm(code, ENTRY)]
    image.md.detail = False
    fn = T.Function(ENTRY, "branch_entry", len(code), ins)
    fn.measure(image)
    tr = T.Translator(image, {ENTRY}, Opts())
    tr.prepare(fn)
    text = "\n".join(tr.translate(fn, (ENTRY + 10,)))
    assert not fn.proven_zero_branches
    assert "CALL" in text


def test_impossible_jne_target_is_removed_with_fallthrough_kept():
    fn, text = translate(bytes.fromhex("31 c0 75 06 b8 01 00 00 00 c3 0f 0b c3"))
    assert fn.proven_zero_branches == {1: False}
    assert "UD2" not in text
    assert "MOV EAX,0x1" in text


def test_known_entry_into_false_branch_target_keeps_its_instruction():
    with pytest.raises(T.TranslateError, match="UD2"):
        translate(bytes.fromhex("31 c0 75 06 b8 01 00 00 00 c3 0f 0b c3"), known=(ENTRY + 10,))


def test_unproven_conditional_gap_retains_its_taken_edge():
    code = bytes.fromhex("74 06 b8 02 00 00 00 c3 b8 01 00 00 00 c3")
    image = synthetic_image({ENTRY: code})
    ins = [i for i in image.recover(ENTRY, set()) if i.addr != ENTRY + 2]
    fn = T.Function(ENTRY, "gap_branch", len(code), ins)
    fn.measure(image)
    tr = T.Translator(image, {ENTRY}, Opts())
    tr.prepare(fn)
    assert fn.index[ENTRY + 8] in tr.reached(fn, {ENTRY})


def test_dead_unknown_jump_does_not_invent_an_alternate_branch_entry():
    fn, text = translate(bytes.fromhex("31 c0 74 02 ff e2 c3"))
    assert fn.proven_zero_branches == {1: True}
    assert ENTRY + 4 in fn.dead_addrs


def test_a_known_entry_into_the_unknown_jump_invalidates_the_branch_proof():
    fn, text = translate(bytes.fromhex("31 c0 74 02 ff e2 c3"), known=(ENTRY + 4,))
    assert not fn.proven_zero_branches


def test_fixed_zero_jump_retains_guest_writes_but_is_not_an_arbitrary_entry():
    code = bytes.fromhex("31 c0 74 08 bc 00 00 00 00 90 ff e4 c3")
    fn, text = translate(code)
    assert fn.proven_fixed_jumps == {4: 0}
    assert fn.proven_zero_branches == {1: True}
    assert {ENTRY + 4, ENTRY + 9, ENTRY + 10} <= fn.dead_addrs


def test_independently_entered_fixed_jump_is_not_assumed_to_have_run_its_mov():
    code = bytes.fromhex("31 c0 74 08 bc 00 00 00 00 90 ff e4 c3")
    fn, text = translate(code, known=(ENTRY + 10,))
    assert not fn.proven_fixed_jumps
    assert not fn.proven_zero_branches
