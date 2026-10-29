import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createDemandReader } from "../web/demand-files.mjs";

const hash = bytes => createHash("sha256").update(bytes).digest("hex");
function fixture() {
  const objects = [Buffer.from("0123456789abcdef"), Buffer.from("GHIJKLMNOPQRSTUV")];
  const chunks = objects.map((bytes, i) => ({ path: `archive.part${i}`, size: bytes.length,
    sha256: hash(bytes), ranges: [hash(bytes)] }));
  const all = Buffer.concat(objects), exe = Buffer.from("exe");
  const game = { id: "test", executable: "game.exe", sha256: hash(exe), requiredDirs: ["models"],
    hosted: { build: "0123456789abcdef" } };
  const inventory = { id: game.id, executableSha256: game.sha256, build: game.hosted.build,
    rangeBlockSize: 4194304, entries: [
      { path: "game.exe", size: 3, sha256: game.sha256, ranges: [game.sha256] },
      { path: "models/gta3.img", size: all.length, sha256: hash(all), chunks },
    ] };
  const requests = [];
  const fetchFile = async (url, options) => {
    const i = Number(url.at(-1)), bytes = objects[i];
    requests.push({ url, range: options.headers.Range });
    await new Promise(resolve => setTimeout(resolve, 2));
    return new Response(bytes, { status: 206, headers: { "Content-Range": `bytes 0-15/16` } });
  };
  return { game, inventory, fetchFile, requests, all };
}
test("stat/open metadata downloads nothing; random reads fetch only intersecting objects", async () => {
  const f = fixture(), reader = createDemandReader(f.game, f.inventory, f);
  assert.equal(reader.size("models/gta3.img"), 32);
  assert.equal(f.requests.length, 0);
  const bytes = new Uint8Array(5);
  assert.equal(await reader.readInto("models/gta3.img", bytes, 18, 5), 5);
  assert.deepEqual(Buffer.from(bytes), f.all.subarray(18, 23));
  assert.equal(f.requests.length, 1);
  assert.match(f.requests[0].url, /part1$/);
  assert.equal(f.requests[0].range, "bytes=0-15");
  await reader.readInto("models/gta3.img", bytes, 17, 5);
  assert.equal(f.requests.length, 1);
});
test("cross-object reads, EOF and concurrent read deduplication preserve exact guest bytes", async () => {
  const f = fixture(), reader = createDemandReader(f.game, f.inventory, f);
  const a = new Uint8Array(8), b = new Uint8Array(8);
  await Promise.all([reader.readInto("models/gta3.img", a, 12, 8), reader.readInto("models/gta3.img", b, 12, 8)]);
  assert.deepEqual(Buffer.from(a), f.all.subarray(12, 20));
  assert.deepEqual(a, b);
  assert.equal(f.requests.length, 2);
  const end = new Uint8Array(8).fill(255);
  assert.equal(await reader.readInto("models/gta3.img", end, 30, 8), 2);
  assert.deepEqual([...end.slice(2)], Array(6).fill(255));
  assert.equal(await reader.readInto("models/gta3.img", end, 33, 8), 0);
});
test("persistent verified blocks work offline; memory eviction is bounded", async () => {
  const f = fixture(), stored = new Map(), cache = { get: async key => stored.get(key),
    set: async (key, value) => stored.set(key, value) };
  const r = createDemandReader(f.game, f.inventory, { ...f, cache, memoryBytes: 16 });
  const out = new Uint8Array(2);
  await r.readInto("models/gta3.img", out, 0, 2);
  await r.readInto("models/gta3.img", out, 18, 2);
  await r.readInto("models/gta3.img", out, 0, 2);
  assert.equal(r.stats.diskHits, 1);
  const offline = createDemandReader(f.game, f.inventory, { cache, fetchFile: async () => { throw Error("offline"); } });
  await offline.readInto("models/gta3.img", out, 18, 2);
  assert.equal(offline.stats.networkBytes, 0);
});
test("corrupt cache is repaired; corrupt network and HTTP 200 cannot fabricate successful reads", async () => {
  const f = fixture();
  const r = createDemandReader(f.game, f.inventory, { ...f, cache: { get: async () => Buffer.alloc(16), set: async () => {} } });
  await r.readInto("models/gta3.img", new Uint8Array(2), 0, 2);
  assert.equal(r.stats.networkBytes, 16);
  for (const fetchFile of [async () => new Response(Buffer.alloc(16), { status: 206, headers: { "Content-Range": "bytes 0-15/16" } }),
    async () => new Response(f.all)]) {
    const bad = createDemandReader(f.game, f.inventory, { fetchFile });
    const out = new Uint8Array(2).fill(255);
    await assert.rejects(bad.readInto("models/gta3.img", out, 0, 2));
    assert.deepEqual([...out], [255, 255]);
    assert.equal(bad.stats.requests, 3);
  }
});
test("unlisted paths and invalid reads fail before networking; fresh Wasm views survive await", async () => {
  const f = fixture(), r = createDemandReader(f.game, f.inventory, f);
  await assert.rejects(r.readInto("../secret", new Uint8Array(2), 0, 2), /Unlisted/);
  await assert.rejects(r.readInto("models/gta3.img", new Uint8Array(2), -1, 2), /Invalid/);
  assert.equal(f.requests.length, 0);
  let target = new Uint8Array(2);
  const old = target;
  const read = r.readInto("models/gta3.img", () => target, 7, 2);
  target = new Uint8Array(2);
  await read;
  assert.deepEqual([...old], [0, 0]);
  assert.equal(Buffer.from(target).toString(), "78");
});

test("failed multi-block reads finish sibling requests before returning a reusable guest buffer", async () => {
  const f = fixture();
  let siblingFinished = false;
  const r = createDemandReader(f.game, f.inventory, { fetchFile: async (url, options) => {
    if (url.endsWith("part0")) return new Response(new Uint8Array(16), {
      status: 206, headers: { "Content-Range": "bytes 0-15/16" },
    });
    await new Promise(resolve => setTimeout(resolve, 25));
    siblingFinished = true;
    return f.fetchFile(url, options);
  } });
  const out = new Uint8Array(32).fill(255);
  await assert.rejects(r.readInto("models/gta3.img", out, 0, 32), /checksum/);
  assert.equal(siblingFinished, true);
  assert.deepEqual([...out], Array(32).fill(255));
});

test("network concurrency is bounded and activity reports return to idle", async () => {
  const f = fixture(), events = [];
  let active = 0, peak = 0;
  const r = createDemandReader(f.game, f.inventory, { concurrency: 1,
    onActivity: stats => events.push({ ...stats }), fetchFile: async (...args) => {
      peak = Math.max(peak, ++active);
      try { return await f.fetchFile(...args); } finally { active--; }
    },
  });
  await r.readInto("models/gta3.img", new Uint8Array(32), 0, 32);
  assert.equal(peak, 1);
  assert.equal(events.at(-1).activeDownloads, 0);
  assert.equal(events.at(-1).networkBytes, 32);
  assert.equal(events.at(-1).failures, 0);
});
