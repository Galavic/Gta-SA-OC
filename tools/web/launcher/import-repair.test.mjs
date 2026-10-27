import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { ensureAuxiliaryFiles } from "../repair-import.mjs";

const bytes = Buffer.from("synthetic auxiliary module");
const file = { name: "sound.dll", size: bytes.length, sha256: createHash("sha256").update(bytes).digest("hex") };
function directory(initial = {}, failWrite = false) {
  const files = new Map(Object.entries(initial));
  return {
    files,
    async getFileHandle(name, { create = false } = {}) {
      if (!files.has(name) && !create) throw new DOMException("missing", "NotFoundError");
      return {
        async getFile() {
          const value = files.get(name);
          return { size: value.length, arrayBuffer: async () => Uint8Array.from(value).buffer };
        },
        async createWritable() {
          let pending;
          return {
            async write(value) { if (failWrite) throw Error("storage full"); pending = Buffer.from(value); },
            async close() { files.set(name, pending); },
            async abort() {},
          };
        },
      };
    },
  };
}
test("missing auxiliary file is copied and reread; unrelated files stay put", async () => {
  const dir = directory({ "save.b": Buffer.from("save"), "gta3.img": Buffer.from("archive") });
  const requested = [];
  const result = await ensureAuxiliaryFiles(dir, [file], {
    fetchFile: async url => { requested.push(url); return new Response(bytes); },
  });
  assert.deepEqual(result, [file.name]);
  assert.deepEqual(requested, ["/install/sound.dll"]);
  assert.deepEqual(dir.files.get(file.name), bytes);
  assert.equal(dir.files.get("save.b").toString(), "save");
  assert.equal(dir.files.get("gta3.img").toString(), "archive");
});
test("matching local file needs no download", async () => {
  const dir = directory({ [file.name]: bytes });
  assert.deepEqual(await ensureAuxiliaryFiles(dir, [file], {
    fetchFile: () => { throw Error("unexpected fetch"); },
  }), []);
});
test("wrong existing file is repaired", async () => {
  const dir = directory({ [file.name]: Buffer.alloc(bytes.length) });
  await ensureAuxiliaryFiles(dir, [file], { fetchFile: async () => new Response(bytes) });
  assert.deepEqual(dir.files.get(file.name), bytes);
});
test("bad downloaded bytes cannot overwrite an existing file", async () => {
  const previous = Buffer.from("old");
  const dir = directory({ [file.name]: previous });
  await assert.rejects(ensureAuxiliaryFiles(dir, [file], {
    fetchFile: async () => new Response(Buffer.alloc(bytes.length)),
  }), /no coincide/);
  assert.deepEqual(dir.files.get(file.name), previous);
});
test("HTTP and write failures stop boot preparation", async () => {
  await assert.rejects(ensureAuxiliaryFiles(directory(), [file], {
    fetchFile: async () => new Response("missing", { status: 404 }),
  }), /HTTP 404/);
  await assert.rejects(ensureAuxiliaryFiles(directory({}, true), [file], {
    fetchFile: async () => new Response(bytes),
  }), /storage full/);
});
test("unsafe file names are refused before reading or downloading", async () => {
  await assert.rejects(ensureAuxiliaryFiles(directory(), [{ ...file, name: "../sound.dll" }]), /Invalid/);
});
