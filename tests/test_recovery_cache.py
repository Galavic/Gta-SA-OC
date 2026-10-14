"""Recovery must remain correct when decoding reuses immutable byte results."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image


def test_recovered_instructions_are_independent_of_prior_mutation():
    entry = 0x00401000
    image = synthetic_image({entry: bytes.fromhex("b8 01 00 00 00 c3")})
    first = image.recover(entry, set())
    expected = [(i.addr, i.mnem, list(i.ops), i.raw) for i in first]
    first[0].ops[0] = "EDX"
    first[0].mnem = "XOR"
    second = image.recover(entry, set())
    assert [(i.addr, i.mnem, i.ops, i.raw) for i in second] == expected


def test_warm_decoding_does_not_override_a_narrower_function_bound():
    entry = 0x00401000
    image = synthetic_image({entry: bytes.fromhex("b8 01 00 00 00 c3")})
    assert len(image.recover(entry, set(), bounds=(entry, entry + 6))) == 2
    assert image.recover(entry, set(), bounds=(entry, entry + 3)) == []
    assert len(image.recover(entry, set(), bounds=(entry, entry + 6))) == 2


def test_replacing_the_image_changes_the_recovered_instruction():
    entry = 0x00401000
    image = synthetic_image({entry: bytes.fromhex("b8 01 00 00 00 c3")})
    before = image.recover(entry, set())
    data = bytearray(image.data)
    data[entry - image.base + 1] = 2
    image.data = bytes(data)
    after = image.recover(entry, set())
    assert before[0].ops != after[0].ops
    assert before[0].ops[0] == after[0].ops[0] == "EAX"


def test_instruction_end_preserves_both_wait_prefix_interpretations():
    entry = 0x00401000
    image = synthetic_image({entry: bytes.fromhex("9b d9 e0 c3")})
    for _ in range(2):
        assert image.insn_end(entry, "WAIT") == entry + 1
        assert image.insn_end(entry, "FCHS") == entry + 3


def test_instruction_end_changes_with_replaced_bytes():
    entry = 0x00401000
    image = synthetic_image({entry: bytes.fromhex("b8 01 00 00 00 c3")})
    assert image.insn_end(entry, "MOV") == entry + 5
    data = bytearray(image.data)
    data[entry - image.base] = 0xB0
    image.data = bytes(data)
    assert image.insn_end(entry, "MOV") == entry + 2
