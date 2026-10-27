"""Preparation must optimise small-local modules and preserve a working build on failure."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "prepare_browser_wasm", Path(__file__).resolve().parents[1] / "prepare_browser_wasm.py")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


def module(functions):
    # Valid no-argument/no-result functions; no excessive locals to trigger the
    # old workaround. An optimizer can legitimately merge identical bodies.
    return (b"\0asm\1\0\0\0\x01\x04\x01\x60\x00\x00"
            + bytes([3, functions + 1, functions]) + bytes(functions)
            + bytes([10, 1 + functions * 3, functions]) + b"\x02\x00\x0b" * functions)


class PreparationTests(unittest.TestCase):
    def prepare_fixture(self, output_count=1, fail=None):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "game.toml").write_text('[game]\napp_name="Game"\nid="test"\n')
        self.source = root / "build/web/recomp/Game.wasm"
        self.site = root / "build/web-site/test/Game.wasm"
        for path in (self.source, self.site):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(module(2))
        sdk = root / "sdk"
        node = sdk / "node/test/node.exe"
        node.parent.mkdir(parents=True)
        node.touch()
        self.calls = []

        def run(command, **kwargs):
            self.calls.append(command)
            optimizer = "wasm-opt" in command[0]
            if fail == ("optimizer" if optimizer else "v8"):
                raise subprocess.CalledProcessError(1, command)
            if optimizer:
                Path(command[command.index("-o") + 1]).write_bytes(module(output_count))
            return subprocess.CompletedProcess(command, 0)

        return root, sdk, run

    def test_optimizes_even_below_local_limit_and_accepts_inlining(self):
        root, sdk, run = self.prepare_fixture()
        with patch.object(PREPARE.subprocess, "run", side_effect=run):
            PREPARE.prepare(sdk, root)
        self.assertIn("-O2", self.calls[0])
        self.assertNotIn("--all-features", self.calls[0])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.source.read_bytes(), module(1))
        self.assertEqual(self.site.read_bytes(), module(1))
        self.assertEqual((self.source.parent / "Game.linked.wasm").read_bytes(), module(2))
        import json
        status = json.loads((root / "build/browser-wasm-status.json").read_text())
        self.assertEqual(status["input_sha256"], hashlib.sha256(module(2)).hexdigest())
        self.assertEqual(status["output_sha256"], hashlib.sha256(module(1)).hexdigest())

    def test_optimizer_and_v8_failures_leave_both_working_artifacts_intact(self):
        for failure in ("optimizer", "v8"):
            with self.subTest(failure=failure):
                root, sdk, run = self.prepare_fixture(fail=failure)
                with patch.object(PREPARE.subprocess, "run", side_effect=run):
                    with self.assertRaises(subprocess.CalledProcessError):
                        PREPARE.prepare(sdk, root)
                self.assertEqual(self.source.read_bytes(), module(2))
                self.assertEqual(self.site.read_bytes(), module(2))

    def test_empty_or_growing_module_is_rejected_before_installation(self):
        for count in (0, 3):
            with self.subTest(functions=count):
                root, sdk, run = self.prepare_fixture(output_count=count)
                with patch.object(PREPARE.subprocess, "run", side_effect=run):
                    with self.assertRaises(AssertionError):
                        PREPARE.prepare(sdk, root)
                self.assertEqual(len(self.calls), 1)
                self.assertEqual(self.source.read_bytes(), module(2))
                self.assertEqual(self.site.read_bytes(), module(2))


if __name__ == "__main__":
    unittest.main()
