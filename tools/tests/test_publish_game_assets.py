"""Synthetic hosted installation packing/upload checks; no game or network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("publish_game_assets", Path(__file__).parents[1] / "publish_game_assets.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class HostedAssetsTests(unittest.TestCase):
    def test_transfer_chunks_reconstruct_original_and_upload_resumes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "gta_sa.exe").write_bytes(b"exe")
            (source / "world.img").write_bytes(b"synthetic archive")
            with patch.object(publish, "CHUNK_SIZE", 4), patch.object(publish, "SINGLE_OBJECT_LIMIT", 5):
                manifest, manifest_path = publish.build_manifest(source, root / "output")
            entry = next(e for e in manifest["entries"] if e["path"] == "world.img")
            reconstructed = b"".join((manifest_path.parent / c["path"]).read_bytes() for c in entry["chunks"])
            self.assertEqual(reconstructed, b"synthetic archive")
            for chunk in entry["chunks"]:
                self.assertEqual(publish.digest(manifest_path.parent / chunk["path"]), chunk["sha256"])
            uploaded = []
            def record(key, path):
                self.assertTrue(path.is_file())
                uploaded.append(key)
            with patch.object(publish, "upload_one", side_effect=record):
                self.assertEqual(publish.upload(manifest, manifest_path, source, jobs=2), 0)
                first = list(uploaded)
                self.assertEqual(publish.upload(manifest, manifest_path, source, jobs=2), 0)
                self.assertEqual(uploaded, first)
            self.assertEqual(len(uploaded), 1 + len(entry["chunks"]))
            self.assertFalse(any(key.endswith("world.img") for key in uploaded))
            state = json.loads((manifest_path.parent / "upload-state.json").read_text())
            self.assertEqual(len(state), len(uploaded))
