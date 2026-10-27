import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../../vendor/recomp-kit/web/player/index.html', import.meta.url), 'utf8');
const source = html.slice(html.indexOf('// Immersive controls:'), html.indexOf('// End immersive controls.'));
function setup({ keyboard = true, rejectFullscreen = false, rejectKeyboard = false } = {}) {
  function target() {
    const listeners = new Map();
    return { hidden: false, addEventListener(type, fn) { listeners.set(type, fn); },
      fire(type, e = {}) { return listeners.get(type)?.(e); }, focus() {} };
  }
  const calls = [], logs = [], button = target(), canvas = target(), document = target(), window = target();
  document.getElementById = () => button;
  document.documentElement = { requestFullscreen() {
    calls.push('fullscreen');
    if (rejectFullscreen) return Promise.reject(new Error('denied'));
    document.fullscreenElement = document.documentElement;
    document.fire('fullscreenchange');
    return Promise.resolve();
  } };
  document.exitFullscreen = async () => { calls.push('exit-fullscreen'); document.fullscreenElement = null; document.fire('fullscreenchange'); };
  canvas.requestPointerLock = () => { calls.push('pointer'); document.pointerLockElement = canvas; document.fire('pointerlockchange'); return Promise.resolve(); };
  document.exitPointerLock = () => { calls.push('exit-pointer'); document.pointerLockElement = null; document.fire('pointerlockchange'); };
  window.Module = { _os_browser_set_pointer_locked(v) { calls.push(`bridge:${v}`); } };
  const navigator = keyboard ? { keyboard: {
    async lock(keys) { assert.deepEqual(Array.from(keys), ['Escape']); calls.push('keyboard'); if (rejectKeyboard) throw new Error('denied'); },
    unlock() { calls.push('unlock'); },
  } } : {};
  vm.runInNewContext(source, { canvas, document, window, navigator, runtimeReady: true, failed: false, record: s => logs.push(s) });
  return { canvas, document, window, button, calls, logs };
}
test('canvas gesture requests fullscreen and pointer; reserves only Escape', async () => {
  const s = setup();
  await s.canvas.fire('click');
  assert.ok(s.calls.indexOf('fullscreen') < s.calls.indexOf('pointer'));
  assert.ok(s.calls.includes('keyboard'));
  assert.ok(s.calls.includes('bridge:1'));
  assert.equal(s.button.hidden, true);
  const before = s.calls.length;
  s.window.fire('keydown', { code: 'Escape' });
  assert.equal(s.calls.length, before, 'short Escape stays available to SDL');
});
test('browser long-Escape/fullscreen exit releases pointer and keyboard without recapture', async () => {
  const s = setup(); await s.canvas.fire('click');
  const captures = s.calls.filter(x => x === 'pointer').length;
  await s.document.exitFullscreen();
  assert.ok(s.calls.includes('unlock'));
  assert.ok(s.calls.includes('bridge:0'));
  assert.equal(s.button.hidden, false);
  assert.equal(s.calls.filter(x => x === 'pointer').length, captures);
});
test('denied fullscreen and unsupported keyboard degrade without failing capture', async () => {
  const s = setup({ keyboard: false, rejectFullscreen: true }); await s.canvas.fire('click');
  assert.ok(s.logs.some(x => x.includes('Pantalla completa no disponible')));
  assert.ok(s.calls.includes('pointer'));
  const t = setup({ keyboard: false }); await t.canvas.fire('click');
  assert.ok(t.logs.some(x => x.includes('no admite mantener Esc')));
});
test('keyboard permission denial is reported; blur releases capture', async () => {
  const s = setup({ rejectKeyboard: true }); await s.canvas.fire('click');
  assert.ok(s.logs.some(x => x.includes('No se pudo reservar Esc')));
  s.window.fire('blur');
  assert.ok(s.calls.includes('unlock'));
  assert.ok(s.calls.includes('exit-pointer'));
});
