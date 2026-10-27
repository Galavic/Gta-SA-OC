// Repair only the small, explicitly configured auxiliary files before boot.
// All bytes come from this local server; original game archives and saves stay put.
async function digest(bytes) {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
    .map(value => value.toString(16).padStart(2, "0")).join("");
}

export async function ensureAuxiliaryFiles(directory, files, { fetchFile = fetch, report = () => {} } = {}) {
  const repaired = [];
  for (const file of files) {
    if (!/^[\w.-]+$/.test(file.name) || !/^[a-f0-9]{64}$/.test(file.sha256) ||
        !Number.isInteger(file.size) || file.size <= 0 || file.size > 8 * 1024 * 1024)
      throw new Error("Invalid auxiliary file metadata");
    let existing;
    try {
      existing = await (await directory.getFileHandle(file.name)).getFile();
    } catch (error) {
      if (error.name !== "NotFoundError") throw error;
    }
    if (existing?.size === file.size && await digest(await existing.arrayBuffer()) === file.sha256)
      continue;
    report(`Preparando archivo requerido: ${file.name}`);
    const response = await fetchFile(`/install/${encodeURIComponent(file.name)}`, {
      cache: "no-store", signal: AbortSignal.timeout(20000),
    });
    if (!response.ok) throw new Error(`${file.name}: HTTP ${response.status}`);
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength !== file.size || await digest(bytes) !== file.sha256)
      throw new Error(`${file.name}: el archivo local no coincide con esta compilacion`);
    const handle = await directory.getFileHandle(file.name, { create: true });
    const writer = await handle.createWritable();
    try {
      await writer.write(bytes);
      await writer.close();
    } catch (error) {
      await writer.abort().catch(() => {});
      throw error;
    }
    if (await digest(await (await handle.getFile()).arrayBuffer()) !== file.sha256)
      throw new Error(`${file.name}: no se pudo comprobar la copia del navegador`);
    repaired.push(file.name);
  }
  return repaired;
}

export async function repairAuxiliaryFiles(directory, game, options) {
  const response = await fetch(new URL("auxiliary-files.json", import.meta.url), { cache: "no-store" });
  if (!response.ok) throw new Error(`Required files inventory: HTTP ${response.status}`);
  const metadata = await response.json();
  if (metadata.id !== game.id || metadata.executableSha256 !== game.sha256)
    throw new Error("Required files inventory belongs to a different executable");
  return ensureAuxiliaryFiles(directory, metadata.files, options);
}
