import hashlib
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "configure_idle_pacing", Path(__file__).resolve().parents[1] / "configure_idle_pacing.py")
PACING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACING)


class IdleConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.raw = bytes.fromhex("83 f8 0e 72 e1 c7 05 4c 70 c1 00 1e 00 00 00")
        (self.root / "game.exe").write_bytes(self.raw)
        self.config = self.root / "game.toml"
        self.original = ('[game]\nsha256="' + hashlib.sha256(self.raw).hexdigest()
                         + '"\ndeveloper_exe="game.exe"\n[translate]\nresumable_stacks=true\n')
        self.config.write_text(self.original)
        identity = patch.object(PACING, "IMAGE_SHA", hashlib.sha256(self.raw).hexdigest())
        identity.start(); self.addCleanup(identity.stop)
        pe = patch.object(PACING.pefile, "PE", return_value=SimpleNamespace(
            OPTIONAL_HEADER=SimpleNamespace(ImageBase=PACING.SITE),
            get_offset_from_rva=lambda rva: 0 if rva == 0 else 5))
        pe.start(); self.addCleanup(pe.stop)

    def test_apply_is_idempotent_and_restore_is_exact(self):
        result = PACING.configure(self.root)
        applied = self.config.read_text()
        self.assertIn(PACING.PATCH, applied)
        self.assertFalse(result["clock_scaled"])
        self.assertEqual(result["gameplay_limit_fps"], 60)
        PACING.configure(self.root)
        self.assertEqual(applied, self.config.read_text())
        PACING.configure(self.root, restore=True)
        self.assertEqual(self.original, self.config.read_text())
        self.assertEqual(self.raw, (self.root / "game.exe").read_bytes())

    def test_changed_image_is_rejected_without_writing_config(self):
        (self.root / "game.exe").write_bytes(b"other executable")
        with self.assertRaisesRegex(ValueError, "pinned"):
            PACING.configure(self.root)
        self.assertEqual(self.original, self.config.read_text())

    def test_changed_instruction_is_rejected_even_with_matching_identity(self):
        for other, message in [(b"\x90" * 15, "comparison/branch"),
                               (self.raw[:5] + b"\x90" * 10, "Frame-limit")]:
            with self.subTest(message=message):
                (self.root / "game.exe").write_bytes(other)
                with patch.object(PACING, "IMAGE_SHA", hashlib.sha256(other).hexdigest()):
                    self.config.write_text(self.original.replace(hashlib.sha256(self.raw).hexdigest(),
                                                                hashlib.sha256(other).hexdigest()))
                    before = self.config.read_text()
                    with self.assertRaisesRegex(ValueError, message):
                        PACING.configure(self.root)
                    self.assertEqual(before, self.config.read_text())

    def test_unrelated_patches_are_preserved(self):
        self.config.write_text(self.original + 'instruction_patches=[{at=123,text="NOP"}]\n')
        before = self.config.read_text()
        for restore in [False, True]:
            with self.assertRaisesRegex(ValueError, "unrelated"):
                PACING.configure(self.root, restore)
            self.assertEqual(before, self.config.read_text())

    def test_partial_local_candidate_upgrades_to_both_changes(self):
        self.config.write_text(self.original.replace('[translate]\n',
            '[translate]\n' + PACING.OLD_COMMENT + '\n' + PACING.OLD_PATCH + '\n'))
        PACING.configure(self.root)
        self.assertIn(PACING.PATCH, self.config.read_text())
        PACING.configure(self.root, restore=True)
        self.assertEqual(self.original, self.config.read_text())


if __name__ == "__main__":
    unittest.main()
