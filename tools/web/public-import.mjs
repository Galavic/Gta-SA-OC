// Public hosting reads game DLLs only from the visitor's own files.
async function digest(file) {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer()))]
    .map(v => v.toString(16).padStart(2, "0")).join("");
}

export async function missingAuxiliaryFiles(directory, files) {
  const names = new Map();
  for await (const [name, handle] of directory.entries())
    if (handle.kind === "file") names.set(name.toLowerCase(), handle);
  const missing = [];
  for (const expected of files) {
    const handle = names.get(expected.name.toLowerCase());
    const file = handle && await handle.getFile();
    if (!file || file.size !== expected.size || await digest(file) !== expected.sha256) {
      missing.push(expected);
    } else if (handle.name !== expected.name) {
      // OPFS is case sensitive; the guest module loader uses configured names.
      await copy(directory, expected.name, file);
    }
  }
  return missing;
}

async function copy(directory, name, file) {
  const writer = await (await directory.getFileHandle(name, { create: true })).createWritable();
  try { await writer.write(file); await writer.close(); }
  catch (error) { await writer.abort().catch(() => {}); throw error; }
}

export async function importAuxiliaryFiles(directory, expected, selected) {
  // Check every selected replacement before changing any existing file.
  const replacements = [];
  for (const file of selected) {
    const entry = expected.find(e => e.name.toLowerCase() === file.name.toLowerCase());
    if (!entry) continue;
    if (file.size !== entry.size || await digest(file) !== entry.sha256)
      throw new Error(`${entry.name} does not match this runtime. Select it from the compatible game installation.`);
    replacements.push([entry.name, file]);
  }
  if (!replacements.length) throw new Error("No required DLLs selected.");
  for (const [name, file] of replacements) await copy(directory, name, file);
  return missingAuxiliaryFiles(directory, expected);
}

export async function repairAuxiliaryFiles(directory, game) {
  const response = await fetch(new URL("auxiliary-files.json", import.meta.url), { cache: "no-store" });
  if (!response.ok) throw new Error("Required file metadata unavailable");
  const metadata = await response.json();
  if (metadata.id !== game.id || metadata.executableSha256 !== game.sha256)
    throw new Error("Imported game and runtime version do not match");
  let missing = await missingAuxiliaryFiles(directory, metadata.files);
  if (!missing.length) return;
  const panel = document.createElement("div");
  panel.style.pointerEvents = "auto";
  const message = document.createElement("p");
  const button = document.createElement("button");
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".dll";
  input.multiple = true;
  input.hidden = true;
  button.textContent = "Select missing DLLs";
  const explain = () => {
    message.textContent = `Missing or incompatible: ${missing.map(f => f.name).join(", ")}. Select these DLLs from the folder containing gta_sa.exe. Your imported game and saves are kept. Files stay in this browser.`;
  };
  explain();
  panel.append(message, button, input);
  document.getElementById("status").textContent = "Complete the game import to continue";
  document.getElementById("status").append(panel);
  await new Promise(resolve => {
    button.onclick = () => { input.value = ""; input.click(); };
    input.onchange = async () => {
      if (!input.files.length) return;
      button.disabled = true;
      try {
        missing = await importAuxiliaryFiles(directory, metadata.files, input.files);
        if (!missing.length) { panel.remove(); resolve(); }
        else explain();
      } catch (error) { message.textContent = error.message; }
      finally { button.disabled = false; }
    };
  });
}
