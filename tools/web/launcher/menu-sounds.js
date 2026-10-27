// Original local frontend effects; no background music or effect on game audio.
export function installMenuSounds(page = document, host = window) {
  const raw = new Map(["highlight", "select"].map(name => [name,
    host.fetch(`original-menu-audio/${name}.wav`).then(response => {
      if (!response.ok) throw new Error(`Menu sound: HTTP ${response.status}`);
      return response.arrayBuffer();
    }).catch(() => null),
  ]));
  let context, gain, ready, hoverVoice, selectVoice;
  let lastHighlight = -Infinity, lastSelect = -Infinity;
  let keyboard = false, selection = Promise.resolve();
  const buffers = new Map();
  async function unlock() {
    if (!context) {
      const Audio = host.AudioContext || host.webkitAudioContext;
      if (!Audio) return Promise.resolve();
      context = new Audio();
      gain = context.createGain(); gain.gain.value = 0.45; gain.connect(context.destination);
      ready = Promise.all([...raw].map(async ([name, pending]) => {
        const bytes = await pending;
        if (bytes) buffers.set(name, await context.decodeAudioData(bytes));
      }));
    }
    // Called directly in the gesture callback, before any await.
    return Promise.all([context.resume(), ready]);
  }
  function play(name) {
    const buffer = buffers.get(name);
    if (!buffer || context?.state !== "running") return 0;
    const source = context.createBufferSource();
    source.buffer = buffer; source.connect(gain);
    if (name === "highlight") {
      hoverVoice?.stop(); hoverVoice = source;
    } else {
      hoverVoice?.stop(); hoverVoice = undefined;
      selectVoice?.stop(); selectVoice = source;
    }
    source.onended = () => {
      source.disconnect();
      if (hoverVoice === source) hoverVoice = undefined;
      if (selectVoice === source) selectVoice = undefined;
    };
    source.start();
    return buffer.duration;
  }
  function control(target) {
    const element = target?.closest?.("button, a.button, summary, [role='button']");
    return element && !element.disabled && element.getAttribute("aria-disabled") !== "true" &&
      !element.closest("[hidden]") ? element : null;
  }
  function highlight(element) {
    const now = host.performance.now();
    if (!element || now - lastSelect < 130 || now - lastHighlight < 45) return;
    lastHighlight = now;
    play("highlight");
  }
  function confirm() {
    const now = host.performance.now();
    // The primary launcher action forwards a click to the library's Play button.
    if (now - lastSelect < 100) return;
    lastSelect = now;
    selection = unlock().then(() => {
      const duration = play("select");
      // Keep the confirmation audible before Play navigates to the game.
      return new Promise(resolve => host.setTimeout(resolve, Math.min(duration * 1000, 250)));
    }).catch(() => {});
  }
  page.addEventListener("pointerdown", () => {
    keyboard = false; unlock().catch(() => {});
  }, true);
  page.addEventListener("keydown", event => {
    keyboard = true;
    if (event.repeat) return;
    unlock().catch(() => {});
    if (event.key === "Enter" && event.target === page.body) confirm();
  }, true);
  page.addEventListener("pointerover", event => {
    const element = control(event.target);
    if (!element || element === control(event.relatedTarget)) return;
    highlight(element);
  }, true);
  page.addEventListener("focusin", event => {
    if (keyboard) highlight(control(event.target));
  }, true);
  page.addEventListener("click", event => {
    if (control(event.target)) confirm();
  }, true);
  return { waitForSelection: () => Promise.race([
    selection, new Promise(resolve => host.setTimeout(resolve, 350)),
  ]) };
}

if (typeof document !== "undefined") window.recompMenuAudio = installMenuSounds();
