// Bootstrap contract checks only: these do not exercise WebGPU or gameplay.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const html = readFileSync(new URL("../../vendor/recomp-kit/web/player/index.html", import.meta.url), "utf8");
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
async function boot({ stamp = "expected", empty = false } = {}) {
  const elements = new Map();
  const element = () => ({ textContent: "", hidden: false, children: [],
    append(...items) { this.children.push(...items); }, addEventListener() {}, focus() {} });
  const folder = { entries() { return { next: async () => ({ done: empty }) }; } };
  const dir = {
    async getDirectoryHandle(name) { return name === "data" ? folder : this; },
    async getFileHandle(name) {
      if (name === ".stamp" && stamp === null) throw new Error("Missing stamp");
      return { getFile: async () => ({ size: 10, text: async () => stamp }) };
    },
  };
  const device = { lost: new Promise(() => {}), handlers: {},
    addEventListener(name, callback) { this.handlers[name] = callback; } };
  const window = { handlers: {}, addEventListener(name, callback) { this.handlers[name] = callback; } };
  const context = {
    window, crossOriginIsolated: true, URLSearchParams,
    location: { pathname: "/test/", search: "" },
    console: { log() {}, warn() {} },
    document: { title: "", body: element(), createElement: element,
      addEventListener() {},
      getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); } },
    navigator: { storage: { getDirectory: async () => dir },
      gpu: { requestAdapter: async () => ({ features: new Set(), limits: {}, requestDevice: async () => device }) } },
    fetch: async () => ({ json: async () => [{id: "test", title: "Test", executable: "game.exe",
      sha256: "expected", requiredDirs: ["data"]}] }),
  };
  vm.runInNewContext(source, context);
  await new Promise(setImmediate);
  return { window, elements, device };
}

test("exe-only import never loads the runtime", async () => {
  const b = await boot({stamp: null});
  assert.equal(b.window.Module, undefined);
  assert.match(b.elements.get("status").textContent, /could not be validated/);
});
test("wrong-image stamp and empty asset folders are refused", async () => {
  for (const options of [{stamp: "wrong"}, {empty: true}]) {
    const b = await boot(options);
    assert.equal(b.window.Module, undefined);
    assert.match(b.elements.get("status").textContent, /could not be validated/);
  }
});
test("engine failure remains visible after empty progress messages", async () => {
  const b = await boot();
  b.window.Module.callMain = () => 3;
  b.window.Module.onRuntimeInitialized();
  b.window.Module.setStatus("");
  assert.match(b.elements.get("status").textContent, /error 3/);
  assert.equal(b.elements.get("diagnostics").open, true);
});
test("WebGPU and asynchronous JavaScript failures are visible", async () => {
  const b = await boot();
  b.device.handlers.uncapturederror({error: {message: "validation failed"}});
  assert.match(b.elements.get("status").textContent, /WebGPU: validation failed/);
  b.window.handlers.unhandledrejection({reason: new Error("worker failed")});
  assert.match(b.elements.get("status").textContent, /WebGPU: validation failed/);
  assert.match(b.elements.get("boot-log").textContent, /worker failed/);
});

test("secondary worker and network errors retain the first game failure", async () => {
  const b = await boot();
  b.window.Module.onAbort("original guest abort");
  b.window.handlers.error({message: "pthread mutex deadlock detected"});
  b.window.handlers.unhandledrejection({reason: new Error("Failed to fetch")});
  b.window.Module.setStatus("");
  assert.match(b.elements.get("status").textContent, /original guest abort/);
  assert.doesNotMatch(b.elements.get("status").textContent, /Failed to fetch|deadlock/);
  assert.match(b.elements.get("boot-log").textContent, /Failed to fetch/);
});
test("stderr is visible and the boot log is bounded", async () => {
  const b = await boot();
  for (let n = 0; n < 250; n++) b.window.Module.printErr(`line ${n}`);
  assert.equal(b.window.recompLog.length, 200);
  assert.equal(b.elements.get("diagnostics").open, true);
  assert.match(b.elements.get("boot-log").textContent, /line 249/);
});
