import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("prepare_cloudflare", Path(__file__).parents[1] / "prepare_cloudflare.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RuntimeGzipTests(unittest.TestCase):
    def test_roundtrip_is_exact_and_independent_of_the_machine_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "private-machine-name.wasm"
            original = b"\0asm\1\0\0\0" + b"runtime sample" * 10000
            source.write_bytes(original)
            first, second = root / "first.gz", root / "second.gz"
            MODULE.gzip_artifact(source, first)
            MODULE.gzip_artifact(source, second)
            self.assertEqual(gzip.decompress(first.read_bytes()), original)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertNotIn(source.name.encode(), first.read_bytes())
            self.assertLess(first.stat().st_size, source.stat().st_size)
