"""Compare borrowed operand conversion against Capstone's public API."""
from pathlib import Path
import sys
import random
import capstone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
import translate as T


def test_operand_views_match_public_api_on_varied_x86_bytes():
    image = synthetic_image({0x00401000: b"\xc3"})
    image.md.detail = True
    rng = random.Random(90407)
    sequences = [bytes.fromhex(v) for v in (
        "64 8b 04 85 78 56 34 12", "66 83 6c 24 18 ff", "d9 44 24 08",
        "f3 a5", "9a 78 56 34 12 27 87", "67 8b 40 08", "0f 01 00",
        "8d 84 8b 00 80 ff ff", "66 68 80 ff", "dd 1c 24")]
    sequences += [rng.randbytes(16) for _ in range(1500)]
    checked = 0
    for code in sequences:
        for ci in image.md.disasm(code, 0x00401000, count=1):
            mnemonic = image.MNEM_ALIAS.get(ci.mnemonic.split()[-1].upper(), ci.mnemonic.split()[-1].upper())
            try:
                public = [image._op_text(ci, op, mnemonic) for op in ci.operands]
            except T.TranslateError:
                try:
                    image.to_insn(ci)
                except T.TranslateError:
                    checked += 1
                    continue
                raise AssertionError("Borrowed conversion accepted an operand the public path refused")
            ins = image.to_insn(ci)
            if ins.rep or mnemonic in T.Translator.STRING_MNEM:
                public = []
            assert ins.ops == public
            assert ins.mnem == mnemonic
            checked += 1
    assert checked > 1000
