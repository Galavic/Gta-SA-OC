# San Andreas Web

A desk-side companion for the GTA San Andreas browser port in this repository. It is a [Deska](https://deska.dev) community panel: a folder of web files with `panel.json`, no build step and no server.

## What it does

- **Play in browser** opens <https://gta.galavic.world/> through `deska.openUrl`.
- **Status** shows a dated snapshot of what the project has verified, with a link to the current `docs/STATUS.md`.
- **My checks** keeps a personal five-item test log in `deska.storage`. It is saved on the computer and is explicitly not an official verification of the port.
- **Source** opens the GitHub repository.

The status snapshot is not a live query. The statuses are in `index.html` (`data-status` rows) and the wording is in `STRINGS` in `app.js`; the snapshot label is in both locales. Update them together and keep them aligned with `docs/STATUS.md` and `docs/progress.json`.

## Permissions

- `open-url`: the three links. Deska asks for consent the first time for each host.
- No network hosts are declared; the panel fetches nothing.
- The test log uses Deska's package storage (256 KB shared by every copy of the panel on the computer). `localStorage`, `indexedDB` and cookies are not available in the sandbox.

## Load it

Open the Panel Library in Deska (`Ctrl+Shift+E` outside macOS), then **Community → Build a panel → Load a folder** and select this folder:

```text
deska/san-andreas-web
```

## Preview

The panel passes the manifest checks and was loaded in Deska's preview host in dark and light themes, in English and Spanish. The checks cover saved state across reloads, the two-step clear, keyboard tab switching and the simulated `openUrl` call. Loading it in Deska itself is still the real runtime test.

From a clone of [deska-panels-examples](https://github.com/0xPasho/deska-panels-examples):

```powershell
npm install
node tools/preview/server.mjs "<path-to-this-repo>/deska/san-andreas-web"
```

The screenshots used for this check are local evidence under `build/deska-panel-20261023/` and are not part of the panel package.

## Scope

This panel is an unofficial community project. It is not affiliated with Rockstar Games. The status snapshot does not claim a complete conversion, 1:1 equivalence, verified missions or stable 60 FPS.
