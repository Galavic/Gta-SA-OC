import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

function transport() {
  const worker = { postMessage() {} };
  const timers = new Map();
  let sequence = 0;
  const source = readFileSync(new URL("../../../vendor/recomp-kit/web/launcher/app.js", import.meta.url), "utf8")
    .split("const cards = new Map();")[0]
    .replace(/^import .*;$/m, "")
    .replace(/const worker = new Worker\(.*;/, "const worker = fakeWorker;");
  const context = vm.createContext({
    fakeWorker: worker,
    setTimeout(fn) { timers.set(++sequence, fn); return sequence; },
    clearTimeout(id) { timers.delete(id); },
  });
  vm.runInContext(source + "\nglobalThis.rpc = call; globalThis.requests = pending;", context);
  return { worker, timers, call: context.rpc, pending: context.requests };
}

test("status deadline rejects without leaving an outstanding request", async () => {
  const t = transport();
  const result = t.call("status");
  const rejected = assert.rejects(result, /checking game files/);
  [...t.timers.values()][0]();
  await rejected;
  assert.equal(t.pending.size, 0);
  t.worker.onmessage({ data: { id: 1, result: "late" } });
  assert.equal(t.pending.size, 0);
});

test("a response clears its deadline; imports have no status deadline", async () => {
  const t = transport();
  const status = t.call("status");
  t.worker.onmessage({ data: { id: 1, result: "ready" } });
  assert.equal(await status, "ready");
  assert.equal(t.timers.size, 0);
  const importing = t.call("import");
  assert.equal(t.timers.size, 0);
  t.worker.onmessage({ data: { id: 2, result: "done" } });
  assert.equal(await importing, "done");
});

test("worker failure releases every waiting action", async () => {
  const t = transport();
  const status = assert.rejects(t.call("status"), /Recarga el launcher/);
  const importing = assert.rejects(t.call("import"), /Recarga el launcher/);
  t.worker.onerror();
  await Promise.all([status, importing]);
  assert.equal(t.pending.size, 0);
  assert.equal(t.timers.size, 0);
});

test("postMessage failure also clears the request", async () => {
  const t = transport();
  t.worker.postMessage = () => { throw new Error("cannot post"); };
  await assert.rejects(t.call("status"), /cannot post/);
  assert.equal(t.pending.size, 0);
  assert.equal(t.timers.size, 0);
});
