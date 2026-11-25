// Live player count in the top bar, from the presence snapshot
// (docs/LIVE_PLAYERS.md). The launcher only reads the snapshot: it never opens
// a socket, so it is not counted and adds no fan-out to the Durable Object.
// The chip stays hidden until the server answers (no presence on a local server).
const IDLE_MS = 60_000, OPEN_MS = 10_000;

export function installLivePlayers(openModal, page = document, host = window) {
  const chip = page.getElementById("live-chip");
  const chipText = page.getElementById("live-chip-text");
  const modal = page.getElementById("live-players");
  if (!chip || !chipText || !modal) return;
  const fields = ["total", "running", "loading"].map(key => [key, page.getElementById(`live-${key}`)]);
  const note = page.getElementById("live-note");
  const noteText = note?.textContent;
  let timer, inflight = false, known = false, failures = 0;

  function render(data) {
    const total = data.total;
    chipText.textContent = `${total} en línea`;
    chip.setAttribute("aria-label", `${total} en línea. Ver jugadores en vivo`);
    chip.dataset.state = total > 0 ? "live" : "empty";
    for (const [key, el] of fields) if (el) el.textContent = String(data[key]);
    if (note) note.textContent = noteText;
    chip.hidden = false;
  }

  function stale() {
    chip.dataset.state = "offline";
    for (const [, el] of fields) if (el) el.textContent = "—";
    if (note) note.textContent = "Sin conexión con el contador. Se vuelve a intentar en un momento.";
  }

  function schedule() {
    host.clearTimeout(timer);
    if (page.hidden) return;
    // A server that never answered is not retried for long.
    if (!known && failures >= 3) return;
    const base = modal.hidden ? IDLE_MS : OPEN_MS;
    timer = host.setTimeout(refresh, failures ? Math.min(base * 2 ** failures, 5 * 60_000) : base);
  }

  async function refresh() {
    if (inflight || page.hidden) return;
    inflight = true;
    try {
      const response = await host.fetch(new URL("api/presence", page.baseURI), { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data?.type !== "presence" || ![data.total, data.running, data.loading].every(Number.isInteger))
        throw new Error("Unexpected presence snapshot");
      known = true;
      failures = 0;
      render(data);
    } catch {
      failures++;
      if (known) stale();
    } finally {
      inflight = false;
      schedule();
    }
  }

  chip.addEventListener("click", () => {
    openModal("live-players");
    refresh();
  });
  // Faster updates while the panel is open; back to idle when it closes.
  new host.MutationObserver(schedule).observe(modal, { attributes: true, attributeFilter: ["hidden"] });
  page.addEventListener("visibilitychange", () => {
    if (page.hidden) host.clearTimeout(timer);
    else refresh();
  });
  host.addEventListener("pagehide", () => host.clearTimeout(timer));
  host.addEventListener("pageshow", event => { if (event.persisted) refresh(); });
  refresh();
}
