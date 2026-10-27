// Synthetic OPFS and HTTP ranges: no browser gameplay claims.
import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { importHostedGame } from "../hosted-import.mjs";

const hash = bytes => createHash("sha256").update(bytes).digest("hex");
class MemoryDirectory {
  constructor(files = new Map(), prefix = "") { this.files = files; this.prefix = prefix; }
  async getDirectoryHandle(name) { return new MemoryDirectory(this.files, this.prefix + name + "/"); }
  async removeEntry(name) {
    if (!this.files.delete(this.prefix + name)) throw new DOMException("missing", "NotFoundError");
  }
  async getFileHandle(name, { create = false } = {}) {
    const path = this.prefix + name, files = this.files;
    if (!files.has(path)) {
      if (!create) throw new DOMException("missing", "NotFoundError");
      files.set(path, Buffer.alloc(0));
    }
    return {
      getFile: async () => new File([files.get(path)], name),
      createSyncAccessHandle: async () => ({
        truncate(size) {
          const bytes = Buffer.alloc(size); files.get(path).copy(bytes); files.set(path, bytes);
        },
        write(bytes, { at }) {
          const old = files.get(path), next = Buffer.alloc(Math.max(old.length, at + bytes.length));
          old.copy(next); next.set(bytes, at); files.set(path, next); return bytes.length;
        },
        flush() {}, close() {},
      }),
    };
  }
}
function fixture({ corrupt = false, fail = false, ignoreRange = false } = {}) {
  const objects = new Map([
    ["game.exe", Buffer.from("synthetic executable")], ["first", Buffer.from("first block")],
    ["second", Buffer.from("second block")], ["data/other", Buffer.from("other data")],
    ["sound.dll", Buffer.from("compatible DLL")],
  ]);
  const obj = path => ({ path, size: objects.get(path).length, sha256: hash(objects.get(path)), ranges: [hash(objects.get(path))] });
  const chunks = [obj("first"), obj("second")], archive = Buffer.concat([objects.get("first"), objects.get("second")]);
  const entries = [obj("game.exe"), { path: "data/archive.bin", size: archive.length, sha256: hash(archive), chunks }, obj("data/other"), obj("sound.dll")];
  const inventory = { id: "test", build: "0123456789abcdef", executableSha256: hash(objects.get("game.exe")), rangeBlockSize: 4194304, entries };
  const game = { id: "test", executable: "game.exe", sha256: inventory.executableSha256, requiredDirs: ["data"],
    requiredFiles: [{ name: "sound.dll", sha256: hash(objects.get("sound.dll")) }],
    hosted: { manifest: "/game-assets.json", build: inventory.build } };
  let active = 0, peak = 0, bodies = 0;
  const requests = [];
  const fetchFile = async (url, options = {}) => {
    if (url === "/game-assets.json") return Response.json(inventory);
    const path = decodeURIComponent(url.split("/").slice(3).join("/"));
    requests.push(path);
    peak = Math.max(peak, ++active);
    await new Promise(resolve => setTimeout(resolve, 5)); active--;
    options.signal?.throwIfAborted();
    if (fail && path === "second") throw new Error("network interrupted");
    const value = objects.get(path), bytes = corrupt && path === "second" ? Buffer.alloc(value.length) : value;
    if (ignoreRange) return new Response(bytes, { status: 200 });
    const result = new Response(bytes, { status: 206, headers: { "Content-Range": `bytes 0-${value.length - 1}/${value.length}` } });
    const read = result.arrayBuffer.bind(result);
    result.arrayBuffer = () => { bodies++; return read(); };
    return result;
  };
  return { game, inventory, fetchFile, requests, archive, counters: () => ({ peak, bodies }) };
}

test("verified ranges download concurrently, preserve other files and skip completed imports", async () => {
  const f = fixture(), root = new MemoryDirectory();
  root.files.set("unrelated-save", Buffer.from("keep"));
  const progress = [];
  const result = await importHostedGame(f.game, root, { ...f, onProgress: p => progress.push(p) });
  assert.equal(result.result, "done");
  assert.ok(f.counters().peak > 1 && f.counters().peak <= 4);
  assert.deepEqual(root.files.get("data/archive.bin"), f.archive);
  assert.equal(root.files.get("unrelated-save").toString(), "keep");
  assert.equal(root.files.get(".stamp").toString().trim(), f.game.sha256);
  assert.equal(progress.at(-1).bytesDone, progress.at(-1).bytesTotal);
  const count = f.requests.length;
  assert.equal((await importHostedGame(f.game, root, f)).copied, 0);
  assert.equal(f.requests.length, count);
});
test("network interruption retains verified blocks and resumes only missing ranges", async () => {
  const root = new MemoryDirectory(), broken = fixture({ fail: true });
  assert.equal((await importHostedGame(broken.game, root, broken)).result, "failed");
  assert.equal(root.files.has(".stamp"), false);
  const partial = JSON.parse(root.files.get(".hosted-blocks.json"));
  assert.deepEqual(partial.files["data/archive.bin"].blocks, [0]);
  const resumed = fixture();
  assert.equal((await importHostedGame(resumed.game, root, resumed)).result, "done");
  assert.ok(!resumed.requests.includes("first"));
  assert.deepEqual(root.files.get("data/archive.bin"), resumed.archive);
});
test("corrupt ranges are never marked complete or used for a stamp", async () => {
  const f = fixture({ corrupt: true }), root = new MemoryDirectory();
  const result = await importHostedGame(f.game, root, f);
  assert.equal(result.result, "failed");
  assert.match(result.error, /checksum/);
  assert.equal(root.files.has(".stamp"), false);
  assert.ok(!JSON.parse(root.files.get(".hosted-blocks.json")).files["data/archive.bin"].blocks.includes(1));
});
test("servers ignoring ranges are refused before buffering their large bodies", async () => {
  const f = fixture({ ignoreRange: true }), root = new MemoryDirectory();
  assert.equal((await importHostedGame(f.game, root, f)).result, "failed");
  assert.equal(f.counters().bodies, 0);
  assert.equal(root.files.has(".stamp"), false);
});
test("wrong inventory and insufficient space refuse preparation before any download", async () => {
  const f = fixture(), root = new MemoryDirectory();
  assert.equal((await importHostedGame(f.game, root, { ...f, freeBytes: 0 })).result, "noSpace");
  f.inventory.executableSha256 = "wrong";
  await assert.rejects(importHostedGame(f.game, root, f), /does not match/);
  assert.equal(f.requests.length, 0);
});

test("a corrupt existing DLL is repaired without redownloading completed archives", async () => {
  const f = fixture(), root = new MemoryDirectory();
  await importHostedGame(f.game, root, f);
  root.files.set("sound.dll", Buffer.alloc(root.files.get("sound.dll").length));
  const start = f.requests.length;
  assert.equal((await importHostedGame(f.game, root, f)).result, "done");
  assert.deepEqual(f.requests.slice(start), ["sound.dll"]);
});
test("cancellation finishes sibling requests before returning and keeps the completion stamp absent", async () => {
  const f = fixture(), root = new MemoryDirectory(), abort = new AbortController();
  const result = await importHostedGame(f.game, root, { ...f, signal: abort.signal, onProgress(p) {
    if (p.filesDone > 0) abort.abort();
  } });
  assert.equal(result.result, "cancelled");
  assert.equal(root.files.has(".stamp"), false);
  assert.equal(f.counters().peak > 0, true);
});
