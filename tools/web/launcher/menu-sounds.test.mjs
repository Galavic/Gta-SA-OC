import test from "node:test";
import assert from "node:assert/strict";
import { installMenuSounds } from "./menu-sounds.js";

function fixture(blocked = false) {
  const handlers = {}, voices = [], delays = [], contexts = [];
  let now = 0;
  const page = { body: {}, addEventListener: (type, handler) => { handlers[type] = handler; } };
  const host = {
    performance: { now: () => now },
    fetch: async url => ({ ok: true, arrayBuffer: async () => Uint8Array.of(url.includes("highlight") ? 1 : 2).buffer }),
    setTimeout(resolve, delay) { delays.push(delay); queueMicrotask(resolve); },
    AudioContext: class {
      constructor() { this.state = "suspended"; contexts.push(this); }
      resume() { if (blocked) return new Promise(() => {}); this.state = "running"; return Promise.resolve(); }
      createGain() { return { gain: {}, connect() {} }; }
      decodeAudioData(bytes) { return Promise.resolve({ id: new Uint8Array(bytes)[0], duration: 0.16 }); }
      createBufferSource() {
        return { connect() {}, disconnect() {}, stop() {}, start() { voices.push(this.buffer.id); } };
      }
    },
  };
  const audio = installMenuSounds(page, host);
  const button = (disabled = false) => ({
    disabled, getAttribute: () => null,
    closest(selector) { return selector === "[hidden]" ? null : this; },
  });
  return { handlers, voices, delays, contexts, page, audio, button, clock(value) { now = value; } };
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test("hover waits for gesture unlock and ignores movement within one button", async () => {
  const f = fixture(), button = f.button();
  f.handlers.pointerover({ target: button });
  assert.equal(f.contexts.length, 0);
  assert.deepEqual(f.voices, []);
  f.handlers.pointerdown(); await tick();
  f.clock(100); f.handlers.pointerover({ target: button });
  assert.deepEqual(f.voices, [1]);
  f.clock(200); f.handlers.pointerover({ target: button, relatedTarget: button });
  assert.deepEqual(f.voices, [1]);
});

test("forwarded Play click confirms once; disabled controls remain silent", async () => {
  const f = fixture(), button = f.button();
  f.handlers.pointerdown(); await tick();
  f.clock(100); f.handlers.click({ target: button });
  f.handlers.click({ target: f.button() }); await tick();
  assert.deepEqual(f.voices, [2]);
  f.clock(300); f.handlers.click({ target: f.button(true) }); await tick();
  assert.deepEqual(f.voices, [2]);
  await f.audio.waitForSelection();
  assert.ok(f.delays.includes(160));
  assert.ok(f.delays.includes(350));
});

test("keyboard navigation highlights and body Enter confirms", async () => {
  const f = fixture();
  f.handlers.keydown({ key: "ArrowDown" }); await tick();
  f.clock(100); f.handlers.focusin({ target: f.button() });
  f.clock(300); f.handlers.keydown({ key: "Enter", target: f.page.body }); await tick();
  assert.deepEqual(f.voices, [1, 2]);
});

test("blocked audio cannot prevent navigation from continuing", async () => {
  const f = fixture(true);
  f.handlers.click({ target: f.button() });
  await f.audio.waitForSelection();
  assert.deepEqual(f.voices, []);
  assert.ok(f.delays.includes(350));
});
