// Add approved local cover filenames here as the launcher gallery grows.
export const backgrounds = ["background.png", "background-2.png", "background-3.png", "background-4.png"];

export function installBackgroundRotation() {
  const layers = [...document.querySelectorAll(".scene .photo")];
  const toggle = document.getElementById("background-toggle");
  if (layers.length < 2 || backgrounds.length < 2 || !toggle) return;
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const loaded = new Map();
  let timer, active = 0, index = 0, revision = 0, userPaused = null, initialized = false;
  let remaining = [];
  const paused = () => userPaused ?? reducedMotion.matches;

  function shuffle(indices) {
    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    return indices;
  }

  function nextCover() {
    if (!remaining.length) {
      remaining = shuffle(backgrounds.map((_, i) => i));
      // A fresh shuffled round must not start with the cover already visible.
      if (remaining[0] === index) [remaining[0], remaining[1]] = [remaining[1], remaining[0]];
    }
    return remaining.shift();
  }

  function preload(src) {
    if (!loaded.has(src)) loaded.set(src, new Promise(resolve => {
      const image = new Image();
      image.onload = async () => {
        try { await image.decode(); resolve(true); }
        catch { resolve(false); }
      };
      image.onerror = () => resolve(false);
      image.src = src;
    }));
    return loaded.get(src);
  }

  function schedule() {
    clearTimeout(timer);
    if (initialized && !paused() && !document.hidden) timer = setTimeout(advance, 8000);
  }

  async function advance() {
    const currentRevision = revision;
    const nextIndex = nextCover();
    const ready = await preload(backgrounds[nextIndex]);
    if (currentRevision !== revision || paused() || document.hidden) return;
    if (ready) {
      index = nextIndex;
      const nextLayer = 1 - active;
      // Keep the previous image underneath; fade only the incoming opaque layer
      // so the middle of the dissolve never reveals the page's dark background.
      layers[nextLayer].style.backgroundImage = `url("${backgrounds[index]}")`;
      layers[nextLayer].style.zIndex = "1";
      layers[active].style.zIndex = "0";
      layers[nextLayer].classList.add("is-visible");
      active = nextLayer;
    }
    schedule();
    if (remaining.length) preload(backgrounds[remaining[0]]);
  }

  function sync() {
    revision++;
    toggle.textContent = paused() ? "Play backgrounds" : "Pause backgrounds";
    toggle.setAttribute("aria-pressed", String(paused()));
    schedule();
  }
  toggle.hidden = false;
  for (const layer of layers) layer.addEventListener("transitionend", event => {
    if (event.target === layers[active] && event.propertyName === "opacity")
      layers[1 - active].classList.remove("is-visible");
  });
  toggle.addEventListener("click", () => { userPaused = !paused(); sync(); });
  document.addEventListener("visibilitychange", sync);
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) userPaused = null;
    sync();
  });
  window.addEventListener("pagehide", () => { revision++; clearTimeout(timer); });
  window.addEventListener("pageshow", schedule);
  sync();
  // Randomize the first cover too; the static CSS image remains until decoded.
  const first = Math.floor(Math.random() * backgrounds.length);
  preload(backgrounds[first]).then(ready => {
    if (ready) {
      index = first;
      layers[active].style.backgroundImage = `url("${backgrounds[first]}")`;
    }
    remaining = shuffle(backgrounds.map((_, i) => i).filter(i => i !== index));
    initialized = true;
    sync();
    preload(backgrounds[remaining[0]]);
  });
}
