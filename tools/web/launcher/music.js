// A local audio file keeps the requested soundtrack independent of video embeds.
export function installLauncherMusic(page = document, host = window) {
  const audio = page.getElementById("launcher-music");
  const button = page.getElementById("music-toggle");
  if (!audio || !button) return;
  const storageKey = "gtasa.launcher.music.muted";
  let muted = false, blocked = false, failed = false, leaving = false, pending;
  try { muted = host.localStorage.getItem(storageKey) === "true"; } catch {}
  audio.loop = true;
  audio.volume = 0.3;
  audio.muted = muted;

  function render() {
    const label = failed ? "Music unavailable" : muted ? "Unmute music" : blocked ? "Play music" : "Mute music";
    button.textContent = label;
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-pressed", String(muted));
    button.disabled = failed;
  }

  function play() {
    if (muted || failed || leaving || page.hidden || !audio.paused || pending) return;
    // Call play directly during the gesture; awaiting anything first can lose
    // the browser's permission to start audible playback on mobile.
    pending = audio.play().then(() => {
      blocked = false;
      if (leaving || page.hidden) audio.pause();
    }).catch(error => {
      if (error.name === "NotAllowedError") blocked = true;
      else if (error.name !== "AbortError") failed = true;
    }).finally(() => { pending = null; render(); });
  }

  button.addEventListener("click", () => {
    if (blocked && !muted) { play(); return; }
    muted = !muted;
    audio.muted = muted;
    try { host.localStorage.setItem(storageKey, String(muted)); } catch {}
    render();
    if (!muted) play();
  });
  const activate = event => {
    if (event.target?.closest?.("#music-toggle")) return;
    if (event.type === "keydown" && !["Enter", " "].includes(event.key)) return;
    play();
  };
  page.addEventListener("pointerdown", activate, true);
  page.addEventListener("keydown", activate, true);
  page.addEventListener("visibilitychange", () => {
    if (page.hidden) audio.pause(); else play();
  });
  host.addEventListener("pagehide", () => { leaving = true; audio.pause(); });
  host.addEventListener("pageshow", () => { leaving = false; play(); });
  audio.addEventListener("error", () => { failed = true; render(); });
  render();
  play();
}
