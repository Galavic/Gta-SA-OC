"""Local import inventory/HTTP checks; no browser or game execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

spec = importlib.util.spec_from_file_location("serve_variant", Path(__file__).parents[1] / "serve_variant.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.prepared = self.root / "prepared"
        self.site = self.root / "site"
        self.prepared.mkdir()
        self.site.mkdir()
        (self.site / "games.json").write_text(json.dumps([{
            "id": serve.GAME_ID, "executable": "game.exe", "requiredDirs": ["data"],
        }]))
        (self.prepared / "game.exe").write_bytes(b"synthetic executable")
        (self.prepared / "data").mkdir()
        (self.prepared / "data/main.dat").write_bytes(b"synthetic asset")

    def tearDown(self):
        self.temp.cleanup()

    def test_inventory_includes_nested_assets(self):
        manifest = serve.import_manifest(self.prepared, self.site)
        self.assertEqual({f["path"] for f in manifest["files"]}, {"game.exe", "data/main.dat"})
        self.assertEqual(sum(f["size"] for f in manifest["files"]), 35)

    def test_empty_required_directory_is_rejected(self):
        (self.prepared / "data/main.dat").unlink()
        with self.assertRaisesRegex(ValueError, "empty or missing"):
            serve.import_manifest(self.prepared, self.site)

    def test_player_staging_ignores_native_test_javascript(self):
        dest = self.site / serve.GAME_ID
        dest.mkdir()
        (dest / "Game.js").write_text("// runtime")
        (dest / "Game.data").write_bytes(b"synthetic resources")
        (dest / "d3d9_ffp_tests.js").write_text("// test runtime")
        serve.stage_player(self.site)
        page = (dest / "index.html").read_text(encoding="utf-8")
        self.assertIn('script.src = "Game.js"', page)
        self.assertNotIn('script.src = "d3d9_ffp_tests.js"', page)

    def test_http_serves_inventory_only_and_isolates_origin(self):
        old = serve.PREPARED
        serve.PREPARED = self.prepared
        server = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        server.manifest = serve.import_manifest(self.prepared, self.site)
        server.import_files = {f["path"] for f in server.manifest["files"]}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/install/data/main.dat") as response:
                self.assertEqual(response.read(), b"synthetic asset")
                self.assertEqual(response.headers["Cross-Origin-Embedder-Policy"], "require-corp")
            for path in ["../game.exe", "%2e%2e/game.exe", "C:%5cprivate", "data/absent"]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + "/install/" + path)
                self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            serve.PREPARED = old


if __name__ == "__main__":
    unittest.main()
