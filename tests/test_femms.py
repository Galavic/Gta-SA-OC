"""AMD MMX exit must translate at an actual decoded instruction boundary."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
from test_translate_insns import Opts
import translate as T


def test_femms_recovery_and_complete_mmx_exit_helper_match_emms():
    entry = 0x00401000
    bodies = []
    for opcode, mnemonic in [(bytes.fromhex("0f 77 c3"), "EMMS"), (bytes.fromhex("0f 0e c3"), "FEMMS")]:
        image = synthetic_image({entry: opcode})
        instructions = image.recover(entry, set(), bounds=(entry, entry + 3))
        assert [ins.mnem for ins in instructions] == [mnemonic, "RET"]
        fn = T.Function(entry, "mmx_exit", len(opcode), instructions)
        fn.measure(image)
        translator = T.Translator(image, {entry}, Opts())
        translator.prepare(fn)
        emitted = "\n".join(translator.translate(fn)).replace(mnemonic, "MMX_EXIT")
        assert "recomp_trap" not in emitted
        bodies.append(emitted)
    assert bodies[0] == bodies[1]
