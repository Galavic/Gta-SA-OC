"""Faults dispatch through CONTEXT and cannot become ordinary fallthrough."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image, translate_entry_fixture
from test_translate_insns import Opts
import translate as T

ENTRY=0x00401000


def test_recovery_stops_on_the_faulting_instruction():
    image=synthetic_image({ENTRY:bytes.fromhex("90 0f 0b b8 01 00 00 00 c3")})
    assert [i.mnem for i in image.recover(ENTRY,set())]==["NOP","UD2"]


def test_ud2_has_no_native_fallthrough_even_in_a_linear_listing(monkeypatch):
    monkeypatch.setattr(T,"RESUMABLE_STACKS",True)
    image=synthetic_image({ENTRY:bytes.fromhex("0f 0b b8 01 00 00 00 c3")})
    fn=T.Function(ENTRY,"fault",8,T.parse_listing_text(f"{ENTRY:08x}  UD2\n{ENTRY+2:08x}  MOV EAX,0x1\n{ENTRY+7:08x}  RET\n"))
    fn.measure(image)
    tr=T.Translator(image,{ENTRY},Opts())
    tr.prepare(fn)
    assert tr.successors(fn,0)==[]
    assert tr.reached(fn,{ENTRY})=={0}
    assert "recomp_illegal_instruction(c, 0x401000u); return;" in "\n".join(tr.translate(fn))


def test_ordinary_translation_cannot_claim_fault_continuation(monkeypatch):
    monkeypatch.setattr(T,"RESUMABLE_STACKS",False)
    image=synthetic_image({ENTRY:bytes.fromhex("0f 0b")})
    fn=T.Function(ENTRY,"fault",2,image.recover(ENTRY,set()))
    fn.measure(image)
    tr=T.Translator(image,{ENTRY},Opts())
    tr.prepare(fn)
    with pytest.raises(T.TranslateError,match="requires resumable stacks"):
        tr.translate(fn)


def test_fault_keeps_flags_visible_to_the_exception_handler():
    assert T.flag_effect(T.parse_listing_text(f"{ENTRY:08x}  UD2\n")[0])==(T.NO_FLAGS,T.ALL_FLAGS)


def test_reachable_fault_gets_a_retry_entry(tmp_path,monkeypatch):
    code=bytes.fromhex("90 0f 0b")
    image=synthetic_image({ENTRY:code})
    image.code_pointers=lambda *a,**kw:(set(),set())
    monkeypatch.setattr(T,"RESUMABLE_STACKS",True)
    translate_entry_fixture(tmp_path,monkeypatch,image,{ENTRY:code})
    assert "0x00401001u" in (tmp_path / "gen/table.c").read_text()
