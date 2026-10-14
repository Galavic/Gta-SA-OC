"""Impossible CALL bytes must not create resumable return entries."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image, translate_entry_fixture
import translate as T


def test_overlapping_call_does_not_publish_an_impossible_return(tmp_path, monkeypatch):
    entry = 0x00601000
    code = bytes.fromhex("50 9c 31 c0 74 01 e8 9d 58 c3 90 90 90 90")
    image = synthetic_image({entry: code}, base=0x00600000)
    image.code_pointers = lambda *a, **kw: (set(), set())
    monkeypatch.setattr(T, "RESUMABLE_STACKS", True)
    text = translate_entry_fixture(tmp_path, monkeypatch, image, {entry: code})
    assert "void fn_0060100b(" not in text
    table = (tmp_path / "gen/table.c").read_text()
    returns = table.split("recomp_call_returns[] = {", 1)[1].split("};", 1)[0]
    assert "0x0060100bu" not in returns
