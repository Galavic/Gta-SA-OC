import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { missingAuxiliaryFiles, importAuxiliaryFiles, repairAuxiliaryFiles } from "../public-import.mjs";

const bytes = Buffer.from("synthetic DLL");
const expected = [{ name: "sound.dll", size: bytes.length,
  sha256: createHash("sha256").update(bytes).digest("hex") }];
const file = (name, data = bytes) => new File([data], name);
function directory(initial = []) {
  const files = new Map(initial.map(f => [f.name, f]));
  const handle = name => ({ name, kind: "file", getFile: async () => files.get(name),
    createWritable: async () => ({ write: async f => files.set(name, f), close: async () => {}, abort: async () => {} }) });
  return { files, async *entries() { for (const name of files.keys()) yield [name, handle(name)]; },
    async getFileHandle(name) { return handle(name); } };
}
test("missing and corrupt DLLs are reported, valid ones pass", async () => {
  assert.deepEqual(await missingAuxiliaryFiles(directory(), expected), expected);
  assert.deepEqual(await missingAuxiliaryFiles(directory([file("sound.dll", Buffer.alloc(bytes.length))]), expected), expected);
  assert.deepEqual(await missingAuxiliaryFiles(directory([file("sound.dll")]), expected), []);
});
test("Windows filename casing is canonicalized for OPFS", async () => {
  const dir = directory([file("SOUND.DLL")]);
  assert.deepEqual(await missingAuxiliaryFiles(dir, expected), []);
  assert.ok(dir.files.has("sound.dll"));
});
test("selecting DLLs repairs only required files and keeps game and saves", async () => {
  const dir = directory([file("game.exe"), file("save.b")]);
  assert.deepEqual(await importAuxiliaryFiles(dir, expected, [file("SOUND.DLL"), file("other.dll")]), []);
  assert.deepEqual([...dir.files.keys()], ["game.exe", "save.b", "sound.dll"]);
});
test("incompatible selections cannot replace existing DLLs", async () => {
  const old = file("sound.dll");
  const dir = directory([old]);
  await assert.rejects(importAuxiliaryFiles(dir, expected, [file("sound.dll", Buffer.alloc(bytes.length))]), /does not match/);
  assert.equal(dir.files.get("sound.dll"), old);
  await assert.rejects(importAuxiliaryFiles(dir, expected, [file("other.dll")]), /No required/);
});

test("boot waits for selection, supports retry and continues after verified repair", async () => {
  const previousDocument = globalThis.document;
  const previousFetch = globalThis.fetch;
  const nodes = [];
  const status = { textContent: "", append() {} };
  globalThis.document = { getElementById: () => status, createElement(tag) {
    const node = { tag, style: {}, append() {}, remove() { this.removed = true; }, click() {} };
    nodes.push(node);
    return node;
  } };
  globalThis.fetch = async () => Response.json({ id: "test", executableSha256: "exe", files: expected });
  try {
    const dir = directory();
    let done = false;
    const boot = repairAuxiliaryFiles(dir, { id: "test", sha256: "exe" }).then(() => { done = true; });
    await new Promise(setImmediate);
    assert.equal(done, false);
    assert.equal(nodes[0].style.pointerEvents, "auto");
    const input = nodes.find(n => n.tag === "input");
    input.files = [file("sound.dll", Buffer.from("wrong"))];
    await input.onchange();
    assert.equal(done, false);
    assert.match(nodes.find(n => n.tag === "p").textContent, /does not match/);
    input.files = [file("SOUND.DLL")];
    await input.onchange();
    await boot;
    assert.equal(done, true);
    assert.ok(nodes[0].removed);
  } finally {
    globalThis.document = previousDocument;
    globalThis.fetch = previousFetch;
  }
});
