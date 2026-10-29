// Verified random-access archive reads. No archive is fetched by stat/open.
import { validateHostedInventory } from "./hosted-import.mjs";

const digest = async bytes => [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
  .map(value => value.toString(16).padStart(2, "0")).join("");

function browserReporter(id) {
  if (typeof self === "undefined" || !globalThis.location || !globalThis.BroadcastChannel) return () => {};
  const channel = new BroadcastChannel("gta-demand-" + id);
  let last = 0, timer;
  return stats => {
    clearTimeout(timer);
    const send = () => { last = performance.now(); channel.postMessage({ ...stats }); };
    if (performance.now() - last >= 100 || stats.error) send();
    else timer = setTimeout(send, 100);
  };
}

export function watchDemandFiles(game, onStats = () => {}) {
  const channel = new BroadcastChannel("gta-demand-" + game.id);
  const badge = document.createElement("div");
  badge.style.cssText = "position:fixed;bottom:52px;left:12px;padding:8px 12px;background:#151515e8;color:#eee;font:14px system-ui;pointer-events:none;z-index:5";
  badge.hidden = true; document.body.append(badge);
  let timer;
  channel.onmessage = ({ data }) => {
    onStats(data);
    if (data.error) {
      clearTimeout(timer); timer = null;
      badge.textContent = "Game data could not be loaded. Check your connection and reload.";
      badge.hidden = false;
    } else if (data.activeDownloads) {
      if (!timer && badge.hidden) timer = setTimeout(() => {
        timer = null; badge.textContent = "Loading game files…"; badge.hidden = false;
      }, 500);
    } else { clearTimeout(timer); timer = null; badge.hidden = true; }
  };
  return () => { clearTimeout(timer); channel.close(); badge.remove(); };
}

export function createDemandReader(game, inventory, { fetchFile = fetch, cache = null,
  memoryBytes = 32 * 1024 * 1024, concurrency = 4, timeoutMs = 45000,
  onActivity = browserReporter(game.id), readLegacyBlock = null } = {}) {
  if (!Number.isInteger(concurrency) || concurrency < 1 || !Number.isSafeInteger(memoryBytes) || memoryBytes < 0)
    throw new Error("Invalid archive cache limits");
  const entries = new Map(validateHostedInventory(game, inventory).map(entry => [entry.path, {
    ...entry, blocks: entry.blocks.map((block, index) => ({ ...block, index, entryPath: entry.path, entryHash: entry.sha256 })),
  }]));
  const legacySource = readLegacyBlock ? Promise.resolve(readLegacyBlock) : (async () => {
    if (typeof self === "undefined" || !globalThis.navigator?.storage?.getDirectory) return null;
    let root = await navigator.storage.getDirectory();
    root = await root.getDirectoryHandle(game.id);
    root = await root.getDirectoryHandle("game");
    return legacyBlockReader(game, root);
  })().catch(() => null);
  const memory = new Map(), pending = new Map(), waiters = [];
  let used = 0, active = 0;
  const stats = { networkBytes: 0, memoryHits: 0, diskHits: 0, legacyHits: 0, requests: 0, failures: 0, activeDownloads: 0 };
  async function slot(fn) {
    if (active >= concurrency) await new Promise(resolve => waiters.push(resolve));
    else active++;
    try { return await fn(); }
    finally { const next = waiters.shift(); if (next) next(); else active--; }
  }
  function remember(key, bytes) {
    if (bytes.length > memoryBytes) return bytes;
    memory.set(key, bytes); used += bytes.length;
    while (used > memoryBytes) {
      const oldest = memory.keys().next().value;
      used -= memory.get(oldest).length; memory.delete(oldest);
    }
    return bytes;
  }
  async function blockBytes(block) {
    const key = inventory.build + "/" + block.sha256;
    if (memory.has(key)) {
      stats.memoryHits++;
      const bytes = memory.get(key); memory.delete(key); memory.set(key, bytes);
      return bytes;
    }
    if (pending.has(key)) return pending.get(key);
    const request = slot(async () => {
      let saved;
      try { saved = await cache?.get(key); } catch { /* Storage is optional. */ }
      if (saved?.length === block.size && await digest(saved) === block.sha256) {
        stats.diskHits++; return remember(key, saved);
      }
      try {
        const source = await legacySource;
        const previous = source && await source(block);
        if (previous?.length === block.size && await digest(previous) === block.sha256) {
          stats.legacyHits++;
          try { await cache?.set(key, previous); } catch { /* The original OPFS block remains usable. */ }
          return remember(key, previous);
        }
      } catch { /* Missing or corrupt old partial data is fetched again. */ }
      stats.activeDownloads++; onActivity(stats);
      try {
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          stats.requests++;
          const url = `/game/${inventory.build}/${block.path.split("/").map(encodeURIComponent).join("/")}`;
          const response = await fetchFile(url, { headers: {
            Range: `bytes=${block.offset}-${block.offset + block.size - 1}`,
          }, cache: "no-store", signal: AbortSignal.timeout(timeoutMs) });
          if (response.status !== 206 || response.headers.get("Content-Range") !==
              `bytes ${block.offset}-${block.offset + block.size - 1}/${block.objectSize}`) {
            await response.body?.cancel();
            throw new Error(`Invalid range response for ${block.path}: HTTP ${response.status}`);
          }
          const bytes = new Uint8Array(await response.arrayBuffer());
          if (bytes.length !== block.size || await digest(bytes) !== block.sha256)
            throw new Error(`Archive checksum mismatch: ${block.path}`);
          stats.networkBytes += bytes.length;
          try { await cache?.set(key, bytes); } catch { /* Continue in memory if storage is full. */ }
          return remember(key, bytes);
        } catch (error) {
          if (attempt === 2) { stats.failures++; stats.error = true; throw error; }
        }
      }
      } finally { stats.activeDownloads--; onActivity(stats); }
    });
    pending.set(key, request);
    try { return await request; } finally { pending.delete(key); }
  }
  return {
    stats,
    size(path) {
      const entry = entries.get(path);
      if (!entry) throw new Error(`Unlisted game file: ${path}`);
      return entry.size;
    },
    async readInto(path, target, offset, length) {
      const entry = entries.get(path);
      if (!entry) throw new Error(`Unlisted game file: ${path}`);
      if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(length) || length < 0)
        throw new Error("Invalid archive read");
      const end = offset + Math.min(length, Math.max(0, entry.size - offset));
      if (end === offset) return 0;
      let copied = 0, next = 0, failure;
      // Only blocks intersecting the requested range are downloaded. The
      // source can span several R2 objects without changing guest offsets.
      const needed = entry.blocks.filter(block => block.fileOffset < end && block.fileOffset + block.size > offset);
      async function worker() {
        while (next < needed.length && !failure) {
          const block = needed[next++];
          try {
            const start = Math.max(offset, block.fileOffset), stop = Math.min(end, block.fileOffset + block.size);
            const bytes = await blockBytes(block);
            if (failure) return;
            // Wasm memory may grow while awaiting HTTP; obtain its current view.
            const out = typeof target === "function" ? target() : target;
            out.set(bytes.subarray(start - block.fileOffset, stop - block.fileOffset), start - offset);
            copied += stop - start;
          } catch (error) { failure ??= error; }
        }
      }
      // Complete sibling writes before returning to C++; after an EIO the
      // guest can reuse/free its destination, which we must never touch later.
      await Promise.all(Array.from({ length: Math.min(concurrency, needed.length) }, () => worker()));
      if (failure) throw failure;
      return copied;
    },
  };
}

export async function legacyBlockReader(game, root) {
  let journal;
  try { journal = JSON.parse(await (await (await root.getFileHandle(".hosted-blocks.json")).getFile()).text()); }
  catch { return null; }
  if (journal.build !== game.hosted.build || !journal.files) return null;
  return async block => {
    const record = journal.files[block.entryPath];
    if (record?.sha256 !== block.entryHash || !Array.isArray(record.blocks) || !record.blocks.includes(block.index)) return null;
    let directory = root;
    const parts = block.entryPath.split("/"), name = parts.pop();
    for (const part of parts) directory = await directory.getDirectoryHandle(part);
    const file = await (await directory.getFileHandle(name)).getFile();
    if (file.size < block.fileOffset + block.size) return null;
    // A verified journal is only a hint: the caller rechecks the actual bytes.
    return new Uint8Array(await file.slice(block.fileOffset, block.fileOffset + block.size).arrayBuffer());
  };
}

export async function browserBlockCache({ maxBytes = 1024 * 1024 * 1024 } = {}) {
  if (!globalThis.caches) return null;
  const cache = await caches.open("gta-demand-blocks-v1");
  const url = key => new URL("/__gta_verified_block/" + key, location.origin).href;
  return {
    async get(key) {
      const response = await cache.match(url(key));
      return response ? new Uint8Array(await response.arrayBuffer()) : null;
    },
    async set(key, bytes) {
      await cache.put(url(key), new Response(bytes));
      // Entries are <= 4 MiB. Bound disk use conservatively, including older builds.
      const keys = await cache.keys(), maxEntries = Math.max(1, Math.floor(maxBytes / (4 * 1024 * 1024)));
      for (const request of keys.slice(0, Math.max(0, keys.length - maxEntries))) await cache.delete(request);
    },
  };
}

export async function streamingInstallation(game, root) {
  let descriptor;
  try { descriptor = JSON.parse(await (await (await root.getFileHandle(".streaming.json")).getFile()).text()); }
  catch (error) { if (error.name === "NotFoundError") return null; throw error; }
  if (!game.hosted?.demandFiles || descriptor.version !== 1 || descriptor.build !== game.hosted.build ||
      descriptor.executableSha256 !== game.sha256) throw new Error("Streaming installation belongs to another runtime");
  const inventory = JSON.parse(await (await (await root.getFileHandle(".streaming-inventory.json")).getFile()).text());
  validateHostedInventory(game, inventory);
  let bytes = 0;
  for (const item of [{ name: game.executable, sha256: game.sha256 }, ...(game.requiredFiles || [])]) {
    let directory = root; const parts = item.name.split("/"), name = parts.pop();
    for (const part of parts) directory = await directory.getDirectoryHandle(part);
    const file = await (await directory.getFileHandle(name)).getFile();
    if (await digest(await file.arrayBuffer()) !== item.sha256) throw new Error(`Bootstrap checksum mismatch: ${item.name}`);
    bytes += file.size;
  }
  return { state: "ready", mode: "streaming", bytes, inventory };
}
