"""Local import inventory/HTTP checks; no browser or game execution."""
import importlib.util
import json
import hashlib
import re
import subprocess
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen, Request
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

    def test_demand_ranges_use_original_offsets_and_refuse_unlisted_or_invalid_reads(self):
        old, old_site = serve.PREPARED, serve.SITE
        serve.PREPARED, serve.SITE = self.prepared, self.site
        server = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        try:
            server.import_files = {"data/main.dat"}
            payload = (self.prepared / "data/main.dat").read_bytes()
            serve.configure_hosted(server, {"build": "0123456789abcdef", "entries": [{
                "path": "data/main.dat", "size": len(payload), "chunks": [
                    {"path": "parts/one", "size": 4}, {"path": "parts/two", "size": len(payload) - 4},
                ],
            }]})
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(Request(base + "/game/0123456789abcdef/parts/two", headers={"Range": "bytes=1-4"})) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), payload[5:9])
                self.assertEqual(response.headers["Content-Range"], f"bytes 1-4/{len(payload) - 4}")
            for path, byte_range, expected in [
                ("parts/two", "bytes=999-1000", 416), ("parts/two", "bytes=0-", 416),
                ("missing", "bytes=0-1", 404), ("../game.exe", "bytes=0-1", 404),
            ]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + "/game/0123456789abcdef/" + path, headers={"Range": byte_range}))
                self.assertEqual(error.exception.code, expected)
        finally:
            server.shutdown()
            server.server_close()
            if 'thread' in locals():
                thread.join()
            serve.PREPARED, serve.SITE = old, old_site

    def test_player_staging_ignores_native_test_javascript(self):
        dest = self.site / serve.GAME_ID
        dest.mkdir()
        (dest / "Game.js").write_text("// runtime")
        (dest / "Game.data").write_bytes(b"synthetic resources")
        (dest / "Game.wasm").write_bytes(b"synthetic executable")
        (dest / "d3d9_ffp_tests.js").write_text("// test runtime")
        (self.root / "game.toml").write_text('[game]\nid="gtasa-singleplayer"\nsha256="test"\n')
        serve.stage_player(self.site, self.root)
        page = (dest / "index.html").read_text(encoding="utf-8")
        self.assertIn('script.src = "Game.js?build=', page)
        self.assertNotIn('script.src = "d3d9_ffp_tests.js"', page)
        self.assertIn('m.ENV.RECOMP_STRICT_UNKNOWN = "1";', page)
        self.assertLess(page.index('m.ENV.RECOMP_STRICT_UNKNOWN = "1";'),
                        page.index('for (const [k, v] of extra)'))
        self.assertIn('await repairAuxiliaryFiles(dir, game', page)
        self.assertLess(page.index('await repairAuxiliaryFiles(dir, game'),
                        page.index('navigator.gpu.requestAdapter'))

    def test_auxiliary_inventory_checks_module_hashes(self):
        module = self.root / "sound.dll"
        module.write_bytes(b"synthetic module")
        sha = hashlib.sha256(module.read_bytes()).hexdigest()
        config = self.root / "game.toml"
        config.write_text('[game]\nid="test"\nsha256="exe"\n'
                          '[modules.aux.sound]\nname="sound.dll"\npath="sound.dll"\n'
                          f'sha256="{sha}"\n')
        serve.stage_auxiliary_files(self.site, self.root)
        inventory = json.loads((self.site / "auxiliary-files.json").read_text())
        self.assertEqual(inventory["files"], [{"name": "sound.dll", "sha256": sha, "size": 16}])
        module.write_bytes(b"wrong module")
        with self.assertRaisesRegex(ValueError, "does not match"):
            serve.stage_auxiliary_files(self.site, self.root)

    def test_launcher_staging_restores_design_and_preserves_local_files(self):
        self.site.mkdir(exist_ok=True)
        (self.site / "background.png").write_bytes(b"local artwork")
        (self.site / "games.json").write_text("[]")
        serve.stage_launcher(self.site, self.prepared, self.root / "assets")
        self.assertEqual((self.site / "index.html").read_bytes(),
                         (serve.ROOT / "tools/web/launcher/index.html").read_bytes())
        self.assertEqual((self.site / "background.png").read_bytes(), b"local artwork")
        self.assertEqual((self.site / "games.json").read_text(), "[]")
        worker = (self.site / "worker.js").read_text(encoding="utf-8")
        self.assertIn('kind === "hosted" && game.hosted.fastRanges', worker)
        self.assertIn('await import("./hosted-import.mjs")', worker)
        self.assertLess(worker.index("return await importHostedGame"), worker.index("let source;"))
        self.assertIn('else if (kind === "hosted") source = await hostedSource', worker)
        self.assertEqual((self.site / "hosted-import.mjs").read_bytes(),
                         (serve.ROOT / "tools/web/hosted-import.mjs").read_bytes())

    def test_player_enables_read_cache_but_preserves_explicit_runtime_overrides(self):
        game = self.site / serve.GAME_ID
        game.mkdir(parents=True)
        for name, data in {"Game.js": b"", "Game.data": b"assets", "Game.wasm": b"test wasm"}.items():
            (game / name).write_bytes(data)
        (self.root / "game.toml").write_text('[game]\nid="test"\nsha256="exe"\n')
        serve.stage_player(self.site, self.root)
        html = (game / "index.html").read_text(encoding="utf-8")
        self.assertIn('m.ENV.RECOMP_READ_PATH_CACHE = "1";', html)
        self.assertLess(html.index('m.ENV.RECOMP_READ_PATH_CACHE = "1"'),
                        html.index('for (const [k, v] of extra)'))
        # Run the actual staged preRun callback: old experiment links and an
        # inherited environment must both retain normal time. Other explicit
        # runtime overrides remain available for controlled profiling.
        body = re.search(r'preRun: \[\(\) => \{([\s\S]*?)\n    \}\],', html).group(1)
        script = ('const run = new Function("Module", "location", "id", "record", "streaming", "game", process.argv[1]);'
                  'const outputs = ["", "?RECOMP_QPC_SCALE=2&RECOMP_READ_PATH_CACHE=0",'
                  '"?RECOMP_QPC_SCALE=8&RECOMP_QPC_SCALE=2&RECOMP_D3D9_SCALE=2&RECOMP_D3D9_STATS=0",'
                  '"?RECOMP_D3D9_FRAME_GROUP_CACHE=0&RECOMP_D3D9_BATCH_UPLOADS=0&RECOMP_D3D9_RENAME_BUFFERS=0"].map(search => {'
                  'const Module={ENV:{RECOMP_QPC_SCALE:"8",RECOMP_D3D9_SCALE:"1"}};'
                  'const logs=[];run(Module,{search},"test",line=>logs.push(line),false,{});'
                  'return {...Module.ENV,logs};});'
                  'console.log(JSON.stringify(outputs));')
        outputs = json.loads(subprocess.check_output(["node", "-e", script, body], text=True))
        self.assertEqual([row["RECOMP_QPC_SCALE"] for row in outputs], ["1", "1", "1", "1"])
        self.assertEqual(outputs[1]["RECOMP_READ_PATH_CACHE"], "0")
        self.assertNotIn("RECOMP_D3D9_SCALE", outputs[0])
        self.assertEqual(json.loads(outputs[0]["logs"][0].split(": ", 1)[1])["renderScale"], "auto")
        for name in ["RECOMP_D3D9_FRAME_GROUP_CACHE", "RECOMP_D3D9_BATCH_UPLOADS",
                     "RECOMP_D3D9_RENAME_BUFFERS"]:
            self.assertEqual(outputs[0][name], "1")
            self.assertEqual(outputs[3][name], "0")
        self.assertEqual(outputs[2]["RECOMP_D3D9_SCALE"], "2")
        self.assertEqual(outputs[2]["RECOMP_D3D9_STATS"], "0")
        self.assertEqual(json.loads(outputs[1]["logs"][0].split(": ", 1)[1])["qpcScale"], "1")
        self.assertEqual((game / "Game.wasm").read_bytes(), b"test wasm")

    def test_http_serves_inventory_only_and_isolates_origin(self):
        old = serve.PREPARED
        old_site = serve.SITE
        serve.PREPARED = self.prepared
        serve.SITE = self.site
        (self.site / "module.mjs").write_text("export const ready = true;")
        (self.site / "menu.ttf").write_bytes(b"synthetic font")
        server = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        server.manifest = serve.import_manifest(self.prepared, self.site)
        server.import_files = {f["path"] for f in server.manifest["files"]}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/module.mjs") as response:
                self.assertEqual(response.headers.get_content_type(), "application/javascript")
                self.assertEqual(response.read(), b"export const ready = true;")
            with urlopen(base + "/menu.ttf") as response:
                self.assertEqual(response.headers.get_content_type(), "font/ttf")
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
            serve.SITE = old_site


if __name__ == "__main__":
    unittest.main()
