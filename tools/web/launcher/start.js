import { installContributorCards } from "./contributors.js";
import { installBackgroundRotation } from "./backgrounds.js";
import { installLauncherMusic } from "./music.js";

installBackgroundRotation();
installLauncherMusic();

const statusLine = document.getElementById("status-line");
const statusText = document.getElementById("status-text");
const playLabel = document.getElementById("play-label");
const startProgress = document.getElementById("start-progress");
const startBar = document.getElementById("start-bar");
const libStorage = document.getElementById("lib-storage");
const menu = document.getElementById("menu");
const menuItems = [...menu.querySelectorAll(".menu-item")];

const STATE_KEYS = {
  "Unavailable": "unavailable",
  "Not imported": "notFound",
  "Wrong version": "wrongVersion",
  "Incomplete": "incomplete",
  "Ready": "ready",
};

function setStatus(text, tone = "") {
  statusText.textContent = text;
  statusLine.classList.toggle("ready", tone === "ready");
  statusLine.classList.toggle("bad", tone === "bad");
}

function setText(node, value) {
  if (node && node.textContent !== value) node.textContent = value;
}

function syncStorage() {
  const text = document.getElementById("storage-text");
  if (text?.textContent.trim()) setText(libStorage, text.textContent);
}

let card = null;
let currentState = "unknown";
let progressActive = false;
let hostedGame = false;

function applyState(state) {
  currentState = state;
  if (progressActive) return;
  if (hostedGame && state !== "ready") {
    setStatus("PREPARING GAME FILES", "");
    playLabel.textContent = "Prepare game";
    return;
  }
  if (state === "ready") {
    setStatus("READY TO PLAY", "ready");
    playLabel.textContent = "Start game";
  } else if (state === "notFound") {
    setStatus("IMPORT YOUR COPY TO START", "bad");
    playLabel.textContent = "Import game";
  } else if (state === "incomplete") {
    setStatus("GAME FILES ARE MISSING", "bad");
    playLabel.textContent = "Complete import";
  } else if (state === "wrongVersion") {
    setStatus("UNSUPPORTED VERSION", "bad");
    playLabel.textContent = "Check files";
  } else if (state === "unavailable") {
    setStatus("COULD NOT CHECK GAME FILES", "bad");
    playLabel.textContent = "Check library";
  } else {
    setStatus("CHECKING FILES…");
    playLabel.textContent = "Start game";
  }
}

function applyStateFromCard() {
  if (!card) return;
  const stateEl = card.querySelector(".state");
  if (!stateEl) return;
  const state = STATE_KEYS[stateEl.textContent.trim()];
  if (state) applyState(state);
}

function syncCard() {
  if (!card) return;
  applyStateFromCard();
  syncStorage();
}

function mirrorProgress() {
  if (!card) return;
  const progress = card.querySelector(".progress");
  if (!progress) return;
  const active = !progress.hidden;
  progressActive = active;
  startProgress.hidden = !active;
  if (!active) {
    if (currentState !== "unknown") applyState(currentState);
    const error = card.querySelector(".message.bad:not([hidden])");
    if (hostedGame && error?.textContent.trim()) {
      setStatus(error.textContent.trim(), "bad");
      playLabel.textContent = "Retry preparation";
    }
    return;
  }
  const bar = progress.querySelector("progress");
  const text = progress.querySelector(".progress-text");
  if (bar) startBar.style.width = `${Math.round((bar.value || 0) * 100)}%`;
  if (text && text.textContent.trim()) statusText.textContent = text.textContent.trim();
}

function select(index, focus = false) {
  const count = menuItems.length;
  if (!count) return;
  const next = ((index % count) + count) % count;
  menuItems.forEach((el, i) => el.classList.toggle("selected", i === next));
  if (focus) menuItems[next].focus();
}

const previousFocus = new Map();

function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal || !modal.hidden) return;
  previousFocus.set(modal, document.activeElement);
  modal.hidden = false;
  const close = modal.querySelector(".panel-close");
  if (close) close.focus();
  if (id === "library") {
    syncCard();
  }
}

function closeModal(modal) {
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  const previous = previousFocus.get(modal);
  previousFocus.delete(modal);
  if (previous && previous.focus) previous.focus();
}

function focusImport() {
  const button = card && card.querySelector(currentState === "unavailable" ? ".retry-status" : ".import-folder");
  if (button) button.focus();
}

function activate(action) {
  if (action === "library") {
    openModal("library");
    return;
  }
  if (action !== "play") return;
  if (hostedGame && currentState !== "ready") {
    if (!progressActive) window.recompLauncher?.importHosted?.(games[0].id);
    return;
  }
  const play = card && card.querySelector(".play");
  if (currentState === "ready" && play && !play.disabled) {
    play.click();
    return;
  }
  openModal("library");
  focusImport();
}

menuItems.forEach((item, index) => {
  item.addEventListener("mouseenter", () => select(index));
  item.addEventListener("focus", () => select(index));
  item.addEventListener("click", () => {
    select(index);
    activate(item.dataset.action);
  });
});

document.getElementById("save-help").addEventListener("click", () => openModal("save-note"));
installContributorCards(openModal);

for (const modal of document.querySelectorAll(".modal")) {
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal(modal);
  });
  for (const button of modal.querySelectorAll("[data-close]")) {
    button.addEventListener("click", () => closeModal(modal));
  }
}

new MutationObserver(syncStorage).observe(document.getElementById("library"), {
  subtree: true,
  childList: true,
  characterData: true,
});

document.addEventListener("keydown", (event) => {
  const modal = document.querySelector(".modal:not([hidden])");
  if (modal) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeModal(modal);
      return;
    }
    if (event.key === "Tab") {
      const focusable = [...modal.querySelectorAll(
        "button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex='-1'])",
      )].filter((el) => el.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    return;
  }
  const inMenu = document.activeElement && document.activeElement.closest && document.activeElement.closest(".menu");
  if ((event.key === "ArrowDown" || event.key === "ArrowUp") && (inMenu || document.activeElement === document.body)) {
    event.preventDefault();
    const selected = menuItems.findIndex((el) => el.classList.contains("selected"));
    select(selected + (event.key === "ArrowDown" ? 1 : -1), true);
  } else if (event.key === "Enter" && document.activeElement === document.body) {
    event.preventDefault();
    const selected = menuItems.findIndex((el) => el.classList.contains("selected"));
    activate(menuItems[Math.max(0, selected)].dataset.action);
  }
});

function waitFor(predicate, timeout = 20000) {
  return new Promise((resolve) => {
    const started = Date.now();
    const tick = () => {
      const value = predicate();
      if (value) resolve(value);
      else if (Date.now() - started >= timeout) resolve(null);
      else setTimeout(tick, 100);
    };
    tick();
  });
}

const games = await fetch("games.json").then((response) => response.json()).catch(() => []);
hostedGame = Boolean(games[0]?.hosted);
card = await waitFor(() => document.querySelector("#games .game"));

if (!games.length) {
  setStatus("NO GAME CONFIGURED", "bad");
} else if (!card) {
  setStatus("LAUNCHER UNAVAILABLE", "bad");
} else {
  const observer = new MutationObserver(() => {
    syncCard();
    mirrorProgress();
  });
  observer.observe(card, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["hidden", "class"],
  });
  if (games[0].requiredFiles?.length && !hostedGame) {
    const repair = document.createElement("button");
    repair.textContent = "Complete DLLs";
    repair.onclick = () => { location.href = `${games[0].id}/`; };
    card.querySelector(".buttons").append(repair);
  }
  syncCard();
  mirrorProgress();
  setTimeout(() => {
    if (currentState === "unknown") setStatus("COULD NOT CHECK GAME FILES", "bad");
  }, 20000);
}
