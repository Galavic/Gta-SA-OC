# Cloudflare hosting

## Live player panel (2026-10-28)

[Player presence](https://gta.galavic.world/jugadores/) is deployed in Worker
`8c6f6be7-9d71-4ff5-8647-a580310bcedf`. The `LIVE_PLAYERS` Durable Object uses
SQLite, WebSocket hibernation and ephemeral session attachments. It counts
player tabs, including startup/menu; panel observers are excluded. See
[Live players](../docs/LIVE_PLAYERS.md) for semantics, timeouts and deployment.
The runtime identity and R2 game objects remain unchanged. Source tests, actual
WebSocket integration, desktop/mobile rendering and automatic reporting from
an actual Chrome player startup passed; exact evidence is in [status](../docs/STATUS.md).

The optional demand-file pipeline is documented in
[Demand files](../docs/DEMAND_FILES.md). It bootstraps executable/DLL identity and
serves verified archive blocks when the runtime reads them. A compatible rebuilt
runtime is required; preparing a candidate does not change the active deployment.
New release manifests also include reproducible gzip variants of Wasm and data.
Upload all runtime objects listed in the manifest before deploying its Worker.

## Custom domain migration complete (2026-10-28)

The current GTA endpoint is [gta.galavic.world](https://gta.galavic.world/), on
the new account. The zone activated at 2026-10-28T22:25:19.181535Z after the user
changed the registrar delegation to leonidas/peaches. The GTA deployment below
is unchanged; its 35 static files, both gzip runtime streams and a real 4 MiB
range were checked again through the custom domain, including hashes and headers.

The apex [galavic.world](https://galavic.world/) serves the copied portfolio as
Workers Static Assets in the new account; all 123 published files were checked.
Both hostnames have trusted TLS and redirect HTTP to HTTPS. Five MX records,
SPF and DMARC are retained. Historical deployments remain available. See
[status](../docs/STATUS.md) for exact identities, evidence and gameplay limits.

## Demand deployment prepared before domain cutover (2026-10-28)

[Open the launcher](https://gta-sa-oc.gta-sa-oc-web.workers.dev/), Worker version
`6ee32817-1083-458c-92a0-4de46a256216`, uses a separate account and private R2
bucket. All 465 game/runtime objects were uploaded to that account before
activation. The previous custom domain remains on the previous account.

Demand mode starts with the engine and 15,735,296 bytes of executable/DLLs;
archive blocks are fetched when read. Wasm/data are served as 36,377,957 bytes
of gzip, decoding to 295,435,942 bytes. A fresh Chrome profile rendered the
original menu with 36,055,243 additional game-block bytes and no reader failures.
Public Chrome checks verified 35 static files, decoded runtime hashes and a
real 4 MiB range. The same public session also reached CJ, HUD and BMX in the initial alley;
short W input produced visible movement with 654,543,442 game-block bytes and
zero reader failures. Full missions, long-session stability and an FPS improvement
are not established by those checks. See [status](../docs/STATUS.md) for identities
and the separate local gameplay evidence. The sections below retain prior releases.

## Previous account: fast preparation (2026-10-24)

Worker `4e246825-35d4-4286-af76-051caf44b917` (2026-10-24) adds 4 MiB ranged
reads over the same R2 objects. The hosted importer uses four bounded downloads,
WebCrypto hashes and a resumable block journal in OPFS. Old complete file imports
are reused. The engine still needs the complete installation before starting;
this is faster preparation, not demand-loaded gameplay.

Generate and retain the range inventory when assembling future releases:

```powershell
.venv/Scripts/python.exe tools/prepare_fast_game_manifest.py --manifest build/game-assets/<game-build>/game-assets.json --output build/game-assets/<game-build>/game-assets.fast.json
.venv/Scripts/python.exe tools/prepare_cloudflare.py --output build/cloudflare-release-<new-name> --game-manifest build/game-assets/<game-build>/game-assets.fast.json
```

No game object upload is needed when adding the index to the existing inventory.
Verify 206, Content-Range, checksums, MIME and isolation after deployment. The
legacy local-folder/ZIP import remains available for non-hosted configurations.

## Latest launcher refresh

Published with the user's authorization on 2026-10-24, Worker version
`cc75e7f4-51c3-49a4-b887-cd752e15d55a`. The release includes the favicon,
contributor social cards and original platform logos, four shuffled covers,
mobile logo centering, corrected background stacking and looping music with
persistent mute. All 33 static assets were checked over HTTPS for exact bytes,
MIME and COOP/COEP. The hosted game build and runtime remain unchanged.
Media stays under ignored build/launcher-assets and is selected explicitly by
the release packager; browser interaction/audio validation is separate.

## Current hosted installation

The user explicitly requested hosting the prepared game files. Release
`8f22e343-0b9a-423a-8246-62a13ff72f7b` serves game build `a033b7fd3a69b951`:
417 files, 5,004,941,035 bytes. The launcher downloads them automatically into
OPFS on first visit and preserves completed files for retries. Saves stay in
its separate local profile. This deployment has no folder/ZIP selection step.

The local server used prepared/rebased DLLs, so importing the original installed
folder was not equivalent to copying the local server's prepared installation.
The hosted manifest now selects the exact prepared files for this runtime.
R2 holds the files outside Git. Large archives use 64 MiB transfer chunks; the
browser verifies chunk/file hashes while streaming them to their original names.
The Worker serves only the manifest's current-build object allowlist.

To prepare a future hosted release, preserve the game manifest argument:

```powershell
.venv/Scripts/python.exe tools/publish_game_assets.py manifest
.venv/Scripts/python.exe tools/publish_game_assets.py upload --build <game-build>
.venv/Scripts/python.exe tools/prepare_cloudflare.py --output build/cloudflare-release-<new-name> --game-manifest build/game-assets/<game-build>/game-assets.json
npx wrangler@4.152.0 deploy --config build/cloudflare-release-<new-name>/wrangler.jsonc
```

Without `--game-manifest`, the packager retains the alternative local-import mode.
The installation itself and its profiles remain excluded from Git. Browser
preparation/gameplay must be verified separately from HTTP and synthetic tests.

## Custom domain

Live endpoint: [https://gta.galavic.world/](https://gta.galavic.world/)
(verified 2026-10-23). The `galavic.world` zone is hosted by Cloudflare on the
Free plan (zone `cfec2730fb45705cb99e6e5af8e8f0f0`, active since
2026-10-23T20:23:35Z). Namecheap delegates to `gracie.ns.cloudflare.com` and
`yahir.ns.cloudflare.com`; the apex keeps its Vercel A record and its
registrar MX/SPF records. Only the nameservers moved.

`gta.galavic.world` is attached as a Worker custom domain to `gta-sa-oc`, not
to the Pages project. The Worker answers plain HTTP with a 301 to HTTPS, and
the page and both runtime objects carry COOP/COEP. The Pages custom domain for
the same hostname is still pending (`CNAME record not set`) and serves no
traffic; remove it from the Pages project if it is no longer needed.

The apex origin itself returns `402 DEPLOYMENT_DISABLED` from Vercel, both
through Cloudflare and directly against `216.198.79.1`; that is a pre-existing
Vercel deployment state, unrelated to this migration.

Verify after any deployment:

```powershell
curl.exe -sS -I https://gta.galavic.world/
curl.exe -sS -I https://gta.galavic.world/runtime/<public-wasm-sha>/GTASASingleplayer.wasm
curl.exe -sS -o NUL -w "%{http_code} %{redirect_url}`n" http://gta.galavic.world/
```

Each origin has its own OPFS. The current deployment downloads its prepared
copy automatically at `https://gta.galavic.world/`; localhost data is not reused.

Prepare future releases with `--target pages`. Pages requires running Wrangler
from the release directory rather than passing a custom configuration path:

```powershell
.venv/Scripts/python.exe tools/prepare_cloudflare.py --target pages --output build/cloudflare-pages-release-YYYYMMDD
cd build/cloudflare-pages-release-YYYYMMDD
npx wrangler@4.152.0 pages deploy assets --project-name gta-galavic --branch main --commit-dirty=true
```

The packager copies `cloudflare/worker.mjs` to `_worker.js`, so a Pages release
also gets the HTTP-to-HTTPS redirect. Verify DNS, TLS and COOP/COEP after every
release; do not mark the hostname active from the Pages configuration alone.

## Original Workers endpoint

Current deployment: [https://gta.galavic.world/](https://gta.galavic.world/),
also reachable at [https://gta-sa-oc.enrimilioano09.workers.dev/](https://gta-sa-oc.enrimilioano09.workers.dev/).

The launcher is deployed as Worker Static Assets; large runtime files are stored
in a private R2 bucket and streamed through the same Worker origin. The Worker
never buffers the complete Wasm in its own memory. Runtime URLs include the public
Wasm SHA-256 and use immutable caching. HTML, scripts and runtime responses carry
COOP/COEP headers for SharedArrayBuffer and browser threads.

## Prepare a release

From the repository root, after staging a verified local browser build:

```powershell
.venv/Scripts/python.exe tools/prepare_cloudflare.py --output build/cloudflare-release-YYYYMMDD
npx wrangler@4.152.0 deploy --dry-run --config build/cloudflare-release-YYYYMMDD/wrangler.jsonc
```

Choose a new ignored release directory for every release. The packager copies an
explicit allowlist, rejects oversized static assets, strips source-machine prefixes
from compiler strings while preserving Wasm byte lengths, and records source/public
artifact identities in release-manifest.json. Verify the sanitized Wasm with V8
before uploading. This check does not verify gameplay.

The allowlist includes selected launcher media, its local CSS font and frontend
button effects. It excludes the installed game executable, game DLLs, model/world
archives, local probes, debug pages, memory dumps and server traces. Generated
runtime artifacts are hosted in R2 with the user's explicit publication authorization;
they remain excluded from Git.

## Publish

Authenticate Wrangler with your own Cloudflare account. R2 must already be enabled.
Create gta-sa-oc-runtime once, then upload the two runtime files with
`wrangler r2 object put --remote`. Use the exact versioned object keys from
release-manifest.json and set application/wasm for Wasm and application/octet-stream
for data. Upload both artifacts before deploying the matching Worker/configuration.

```powershell
npx wrangler@4.152.0 deploy --config build/cloudflare-release-YYYYMMDD/wrangler.jsonc
```

Do not deploy the local web-site directory directly. That directory can contain
unrelated probes and private material and exceeds the static-asset size limit.

## Alternative local-import mode and checks

When built without `--game-manifest`, each browser imports its compatible
prepared game folder into OPFS. The hosting
provides no /install endpoint and receives no game uploads or browser boot logs.
All four local audio DLLs must match auxiliary-files.json; the local server's
automatic DLL repair is intentionally replaced with local validation on public
hosting. The launcher checks the actual DLL hashes before enabling Play. Use
`Complete DLLs` in the library, then `Select missing DLLs` in the player to
complete an existing import from local files without importing the large game
archives again. Compatible DLLs with different filename casing are copied to the
canonical OPFS names. A new domain has separate OPFS data and therefore needs its own import.

After deployment verify asset hashes, runtime hashes, application/wasm MIME,
COOP/COEP on both launcher and runtime, and rejection of /install and unexpected
runtime object names. Record browser gameplay separately after a real import.

Keep credentials in Wrangler's local profile or environment, never in Git, the
release manifest or public assets. Use tools/check_publication.py before Git pushes.

Folder and ZIP imports automatically copy required DLLs under their canonical
OPFS names and verify their hashes before completing the import. Missing DLLs
are reported before copying large files. Reimporting repairs corrupt DLLs even
when their manifest size and timestamp still match. The selected installation
must contain the compatible DLLs; no extra selection is needed for a full copy.
