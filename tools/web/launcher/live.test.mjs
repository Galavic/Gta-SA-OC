import test from "node:test";
import assert from "node:assert/strict";
import { installLivePlayers } from "./live.js";

function element(extra = {}) {
  const attributes = {}, handlers = {};
  return {
    hidden: true, textContent: "", dataset: {}, ...extra,
    setAttribute(name, value) { attributes[name] = value; },
    getAttribute: name => attributes[name],
    addEventListener(type, handler) { handlers[type] = handler; },
    handlers,
  };
}

function fixture(responses) {
  const ids = {
    "live-chip": element(), "live-chip-text": element(), "live-players": element(),
    "live-total": element(), "live-running": element(), "live-loading": element(),
    "live-note": element({ textContent: "note" }),
  };
  const timers = [], requests = [], opened = [];
  const page = {
    hidden: false, baseURI: "https://example.test/",
    getElementById: id => ids[id] ?? null,
    addEventListener() {},
  };
  const host = {
    fetch: async url => {
      requests.push(String(url));
      const next = responses.shift();
      if (next instanceof Error) throw next;
      return { ok: next.status === undefined, status: next.status ?? 200, json: async () => next };
    },
    setTimeout(fn, delay) { timers.push(delay); return timers.length; },
    clearTimeout() {},
    addEventListener() {},
    MutationObserver: class { observe() {} },
  };
  installLivePlayers(id => { opened.push(id); ids[id].hidden = false; }, page, host);
  return { ids, timers, requests, opened };
}
const tick = () => new Promise(resolve => setImmediate(resolve));
const snapshot = (total, running, loading) => ({ type: "presence", at: 1, total, running, loading, sessions: [] });

test("shows the count once the presence snapshot answers", async () => {
  const f = fixture([snapshot(3, 2, 1)]);
  await tick();
  assert.deepEqual(f.requests, ["https://example.test/api/presence"]);
  assert.equal(f.ids["live-chip"].hidden, false);
  assert.equal(f.ids["live-chip-text"].textContent, "3 en línea");
  assert.equal(f.ids["live-chip"].dataset.state, "live");
  assert.deepEqual(["total", "running", "loading"].map(k => f.ids[`live-${k}`].textContent), ["3", "2", "1"]);
  assert.equal(f.timers.at(-1), 60_000);
});

test("stays hidden and stops asking when the server has no presence", async () => {
  const f = fixture([{ status: 404 }, { status: 404 }, { status: 404 }]);
  await tick();
  assert.equal(f.ids["live-chip"].hidden, true);
  assert.equal(f.timers.at(-1), 120_000);
  f.ids["live-chip"].handlers.click(); await tick();
  assert.equal(f.timers.at(-1), 40_000, "second failure: one more, slower retry");
  const before = f.timers.length;
  f.ids["live-chip"].handlers.click(); await tick();
  assert.equal(f.ids["live-chip"].hidden, true);
  assert.equal(f.timers.length, before, "no retry after three failures");
});

test("opening the panel refreshes; a lost server marks the numbers stale", async () => {
  const f = fixture([snapshot(0, 0, 0), new Error("offline")]);
  await tick();
  assert.equal(f.ids["live-chip"].dataset.state, "empty");
  f.ids["live-chip"].handlers.click(); await tick();
  assert.deepEqual(f.opened, ["live-players"]);
  assert.equal(f.requests.length, 2);
  assert.equal(f.ids["live-chip"].dataset.state, "offline");
  assert.equal(f.ids["live-total"].textContent, "—");
  assert.equal(f.ids["live-chip"].hidden, false);
  assert.equal(f.timers.at(-1), 20_000, "open panel retries sooner, with backoff");
});

test("rejects malformed snapshots", async () => {
  const f = fixture([{ type: "presence", total: "many" }]);
  await tick();
  assert.equal(f.ids["live-chip"].hidden, true);
});
