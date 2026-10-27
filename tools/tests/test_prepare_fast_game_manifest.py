"""Verify range indexing against synthetic source/object identities."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("prepare_fast_game_manifest", Path(__file__).parents[1] / "prepare_fast_game_manifest.py")
fast = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fast)


class FastManifestTests(unittest.TestCase):
    def test_ranges_follow_existing_object_boundaries_without_new_uploads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = b"abcdefghijklm"
            (root / "world.img").write_bytes(data)
            sha = lambda b: hashlib.sha256(b).hexdigest()
            chunks = [{"path": "chunk1", "size": 8, "sha256": sha(data[:8])},
                      {"path": "chunk2", "size": 5, "sha256": sha(data[8:])}]
            source = root / "input.json"
            source.write_text(json.dumps({"build": "same", "entries": [
                {"path": "world.img", "size": 13, "sha256": sha(data), "chunks": chunks}]}))
            output = root / "output.json"
            with patch.object(fast, "BLOCK_SIZE", 4):
                fast.prepare(source, root, output)
            result = json.loads(output.read_text())
            self.assertEqual(result["build"], "same")
            self.assertEqual(result["entries"][0]["chunks"][0]["ranges"], [sha(b"abcd"), sha(b"efgh")])
            self.assertEqual(result["entries"][0]["chunks"][1]["ranges"], [sha(b"ijkl"), sha(b"m")])

    def test_wrong_prepared_bytes_cannot_generate_a_fast_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "game.exe").write_bytes(b"wrong")
            source = root / "input.json"
            source.write_text(json.dumps({"entries": [{"path": "game.exe", "size": 5, "sha256": "0" * 64}]}))
            with self.assertRaisesRegex(ValueError, "differs from inventory"):
                fast.prepare(source, root, root / "output.json")
            self.assertFalse((root / "output.json").exists())
