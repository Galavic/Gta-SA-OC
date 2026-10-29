// Hosted-only fast preparation. Every downloaded 4 MiB range is verified by
// WebCrypto, written at its original offset, and checkpointed for later retries.
const MANIFEST = ".manifest.json", PARTIAL = ".hosted-blocks.json", STAMP = ".stamp";
const HASH = /^[a-f0-9]{64}$/;
const safePath = path => typeof path === "string" && !/[\\:\x00-\x1f\x7f]/.test(path) &&
  path.split("/").every(part => part && part !== "." && part !== "..");

async function fileFor(root, path, create = false) {
  const parts = path.split("/"), name = parts.pop();
  for (const part of parts) root = await root.getDirectoryHandle(part, { create });
  return root.getFileHandle(name, { create });
}
async function readJSON(root, name, fallback) {
  try { return JSON.parse(await (await (await root.getFileHandle(name)).getFile()).text()); }
  catch (error) { if (error.name === "NotFoundError") return fallback; throw error; }
}
async function writeText(root, name, text) {
  const handle = await (await root.getFileHandle(name, { create: true })).createSyncAccessHandle();
  try {
    const bytes = new TextEncoder().encode(text);
    handle.truncate(0);
    if (handle.write(bytes, { at: 0 }) !== bytes.length) throw new DOMException("short write", "QuotaExceededError");
    handle.flush();
  } finally { handle.close(); }
}
async function sha256(bytes) {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
    .map(value => value.toString(16).padStart(2, "0")).join("");
}
export function blocksFor(entry, blockSize) {
  let fileOffset = 0;
  const blocks = [];
  for (const object of entry.chunks || [entry]) {
    if (!safePath(object.path) || !Number.isSafeInteger(object.size) || object.size < 0 ||
        !Array.isArray(object.ranges) || object.ranges.length !== Math.ceil(object.size / blockSize))
      throw new Error("Invalid hosted range inventory");
    for (let i = 0; i < object.ranges.length; i++) {
      if (!HASH.test(object.ranges[i])) throw new Error("Invalid hosted range checksum");
      const offset = i * blockSize, size = Math.min(blockSize, object.size - offset);
      blocks.push({ path: object.path, offset, size, objectSize: object.size,
        fileOffset: fileOffset + offset, sha256: object.ranges[i] });
    }
    fileOffset += object.size;
  }
  if (fileOffset !== entry.size) throw new Error("Hosted ranges do not cover the original file");
  return blocks;
}

export function validateHostedInventory(game, inventory) {
  if (inventory.id !== game.id || inventory.executableSha256 !== game.sha256 ||
      inventory.build !== game.hosted.build || !/^[a-f0-9]{16}$/.test(inventory.build) ||
      inventory.rangeBlockSize !== 4 * 1024 * 1024 || !Array.isArray(inventory.entries))
    throw new Error("Hosted range inventory does not match this runtime");
  const seen = new Set();
  const entries = inventory.entries.map(entry => {
    if (!safePath(entry.path) || entry.path.startsWith(".") || seen.has(entry.path) ||
        !HASH.test(entry.sha256) || !Number.isSafeInteger(entry.size) || entry.size < 0)
      throw new Error("Invalid hosted file inventory");
    seen.add(entry.path);
  return { ...entry, blocks: blocksFor(entry, inventory.rangeBlockSize) };
  });
  if (!entries.some(e => e.path === game.executable && e.sha256 === game.sha256) ||
      (game.requiredDirs || []).some(dir => !entries.some(e => e.path.startsWith(dir + "/"))) ||
      (game.requiredFiles || []).some(file => !entries.some(e => e.path === file.name && e.sha256 === file.sha256)))
    throw new Error("Hosted game is incomplete or its DLLs do not match");
  return entries;
}

export async function importHostedGame(game, root, { fetchFile = fetch, signal, freeBytes,
  onProgress = () => {}, parallelFiles = 2, parallelBlocks = 2, bootstrapOnly = false } = {}) {
  const response = await fetchFile(game.hosted.manifest, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`Game inventory: HTTP ${response.status}`);
  const inventory = await response.json();
  const allEntries = validateHostedInventory(game, inventory);
  const identities = new Set([game.executable, ...(game.requiredFiles || []).map(file => file.name)]);
  const entries = bootstrapOnly ? allEntries.filter(entry => identities.has(entry.path)) : allEntries;

  const manifest = await readJSON(root, MANIFEST, { files: {} });
  let partial = await readJSON(root, PARTIAL, null);
  if (partial?.build !== inventory.build) partial = { build: inventory.build, files: {} };
  let copied = 0, skipped = 0, cursor = 0, needed = 0, failure;
  const progress = { filesDone: 0, filesTotal: entries.length, bytesDone: 0,
    bytesTotal: entries.reduce((sum, entry) => sum + entry.size, 0), current: "" };
  const pending = [];
  const identity = new Map([[game.executable, game.sha256], ...(game.requiredFiles || []).map(f => [f.name, f.sha256])]);
  for (const entry of entries) {
    let size = -1;
    try { size = (await (await fileFor(root, entry.path)).getFile()).size; }
    catch (error) { if (error.name !== "NotFoundError") throw error; }
    const saved = manifest.files[entry.path];
    let complete = size === entry.size && saved?.size === entry.size && saved.sha256 === entry.sha256;
    if (complete && identity.has(entry.path)) {
      complete = await sha256(await (await (await fileFor(root, entry.path)).getFile()).arrayBuffer()) === identity.get(entry.path);
      if (!complete) delete partial.files[entry.path];
    }
    if (complete) {
      skipped++; progress.filesDone++; progress.bytesDone += entry.size;
      continue;
    }
    const savedBlocks = partial.files[entry.path];
    const verified = new Set(savedBlocks?.sha256 === entry.sha256 ? savedBlocks.blocks : []);
    for (const index of [...verified]) {
      const block = entry.blocks[index];
      if (!Number.isInteger(index) || index < 0 || !block || size < block.fileOffset + block.size) verified.delete(index);
    }
    for (const index of verified) progress.bytesDone += entry.blocks[index].size;
    needed += Math.max(0, entry.size - Math.max(0, size));
    pending.push({ entry, verified });
  }
  if (freeBytes !== undefined && needed + (game.minFreeMb || 0) * 1024 * 1024 > freeBytes)
    return { result: "noSpace", needed, free: freeBytes };
  try { await root.removeEntry(STAMP); }
  catch (error) { if (error.name !== "NotFoundError") throw error; }
  onProgress({ ...progress });

  const abort = new AbortController();
  const downloadSignal = signal ? AbortSignal.any([signal, abort.signal]) : abort.signal;
  let checkpointQueue = Promise.resolve(), lastCheckpoint = 0, lastProgress = 0, downloadedBytes = 0;
  const started = performance.now();
  const checkpoint = (force = false) => {
    const now = performance.now();
    if (!force && now - lastCheckpoint < 1000) return checkpointQueue;
    lastCheckpoint = now;
    checkpointQueue = checkpointQueue.then(async () => {
      await writeText(root, PARTIAL, JSON.stringify(partial));
      await writeText(root, MANIFEST, JSON.stringify(manifest));
    });
    return checkpointQueue;
  };
  function report(force = false) {
    const now = performance.now();
    if (force || now - lastProgress >= 150) {
      lastProgress = now;
      onProgress({ ...progress, bytesPerSecond: downloadedBytes / Math.max(0.001, (now - started) / 1000) });
    }
  }
  async function download(block) {
    const path = block.path.split("/").map(encodeURIComponent).join("/");
    const range = `bytes=${block.offset}-${block.offset + block.size - 1}`;
    for (let attempt = 0; ; attempt++) {
      downloadSignal.throwIfAborted();
      try {
        const r = await fetchFile(`/game/${inventory.build}/${path}`, {
          headers: { Range: range }, signal: AbortSignal.any([downloadSignal, AbortSignal.timeout(45000)]),
        });
        if (r.status !== 206 || r.headers.get("Content-Range") !==
            `bytes ${block.offset}-${block.offset + block.size - 1}/${block.objectSize}`) {
          await r.body?.cancel();
          throw new Error(`${block.path}: ranged download failed (HTTP ${r.status})`);
        }
        const bytes = new Uint8Array(await r.arrayBuffer());
        if (bytes.byteLength !== block.size || await sha256(bytes) !== block.sha256)
          throw new Error(`${block.path}: range checksum mismatch`);
        return bytes;
      } catch (error) {
        if (downloadSignal.aborted || attempt >= 2) throw error;
      }
    }
  }
  async function prepareFile({ entry, verified }) {
    const handle = await (await fileFor(root, entry.path, true)).createSyncAccessHandle();
    let next = 0;
    try {
      if (!verified.size) handle.truncate(0);
      partial.files[entry.path] = { sha256: entry.sha256, blocks: [...verified] };
      const jobs = entry.blocks.map((block, index) => ({ block, index })).filter(job => !verified.has(job.index));
      async function worker() {
        try {
        while (next < jobs.length && !downloadSignal.aborted) {
          const { block, index } = jobs[next++];
          progress.current = entry.path;
          const bytes = await download(block);
          downloadSignal.throwIfAborted();
          if (handle.write(bytes, { at: block.fileOffset }) !== bytes.length)
            throw new DOMException("short write", "QuotaExceededError");
          handle.flush();
          verified.add(index);
          partial.files[entry.path].blocks = [...verified];
          progress.bytesDone += bytes.length;
          downloadedBytes += bytes.length;
          report();
          await checkpoint();
        }
        } catch (error) {
          failure ??= error;
          abort.abort(error);
          throw error;
        }
      }
      // Wait for sibling requests before closing their shared file handle.
      const results = await Promise.allSettled(Array.from({ length: Math.min(parallelBlocks, jobs.length) }, () => worker()));
      const rejected = results.find(result => result.status === "rejected");
      if (rejected) throw rejected.reason;
      downloadSignal.throwIfAborted();
      handle.truncate(entry.size); handle.flush();
    } finally { handle.close(); }
    manifest.files[entry.path] = { size: entry.size, mtime: 0, sha256: entry.sha256 };
    delete partial.files[entry.path];
    copied++; progress.filesDone++;
    await checkpoint(true);
    report(true);
  }
  async function fileWorker() {
    while (cursor < pending.length && !downloadSignal.aborted) {
      const item = pending[cursor++];
      try { await prepareFile(item); }
      catch (error) { failure ??= error; abort.abort(error); }
    }
  }
  await Promise.all(Array.from({ length: Math.min(parallelFiles, pending.length) }, () => fileWorker()));
  await checkpoint(true);
  if (signal?.aborted) return { result: "cancelled", copied, skipped };
  if (failure) return { result: failure.name === "QuotaExceededError" ? "noSpace" : "failed", error: failure.message };
  // Check the actual small images the runtime identity depends on, including
  // existing imports. Large archives were verified per range before each write.
  for (const [name, expected] of [[game.executable, game.sha256], ...(game.requiredFiles || []).map(f => [f.name, f.sha256])]) {
    if (await sha256(await (await (await fileFor(root, name)).getFile()).arrayBuffer()) !== expected)
      return { result: "incomplete", missing: [name] };
  }
  if (bootstrapOnly) {
    // A bootstrap never receives the full-installation stamp. Older runtimes
    // must refuse it rather than read holes as valid archive data.
    const bootstrap = new Set(entries.map(entry => entry.path));
    const mountLines = [];
    for (const entry of allEntries) {
      // Fully imported archives stay local; partial files are never exposed.
      const saved = manifest.files[entry.path];
      let local = bootstrap.has(entry.path);
      if (!local && saved?.size === entry.size && saved.sha256 === entry.sha256) {
        try { local = (await (await fileFor(root, entry.path)).getFile()).size === entry.size; }
        catch (error) { if (error.name !== "NotFoundError") throw error; }
      }
      mountLines.push(`${local ? "L" : "R"}\t${entry.path}\n`);
    }
    const mounts = mountLines.join("");
    await writeText(root, ".streaming-inventory.json", JSON.stringify(inventory));
    await writeText(root, ".streaming-game.json", JSON.stringify(game));
    await writeText(root, ".streaming-mount", mounts);
    await writeText(root, ".streaming.json", JSON.stringify({ version: 1, build: inventory.build,
      executableSha256: game.sha256, manifest: game.hosted.manifest }));
  } else {
    try { await root.removeEntry(".streaming.json"); }
    catch (error) { if (error.name !== "NotFoundError") throw error; }
    await writeText(root, STAMP, game.sha256 + "\n");
  }
  report(true);
  return { result: "done", copied, skipped };
}
