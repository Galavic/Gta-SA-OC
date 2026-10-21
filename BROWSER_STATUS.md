# Local browser build

Current revision: the witnessed `014deef0` startup constructor and both
external counter-reset paths are compiled into the served module. Build and
full V8 validation passed. The browser has not yet verified this revision;
the game is still not established as playable. Earlier results follow.

The GTA installation importer reads the verified `prepared` directory through
the loopback server, then uses the launcher's existing OPFS import and SHA-256
checks. Original game files are not modified. Reloading the launcher resumes
an incomplete import; an already imported game is kept.

The first linked Wasm failed V8 compilation because `body_006ab400` had 68,558
locals. Diagnostic `chunk_080.c` now uses backend O1 register allocation with
LLVM IR passes disabled, avoiding both the browser local limit and the expensive
IR optimization of that chunk. The other objects retain their existing options.

The rebuilt module has at most 2,929 locals and passed full V8 compilation.
Debug sections are stripped without changing the code or data sections. The
published Wasm is 208,731,538 bytes. This verifies module compilation, not game
startup, rendering or playable performance.

Run `.venv/Scripts/python.exe build.py --target web --jobs 4 --diagnostic-chunks chunk_080.c --background`
to reproduce. The wrapper calls `prepare_browser_wasm.py` and records its V8
validation in `build/browser-wasm-status.json`. The original first linked
binary is preserved as `build/web/recomp/GTASARecomp.linked.wasm`.

Run `.venv/Scripts/python.exe serve_web_game.py --port 8766` to serve
http://127.0.0.1:8766/. Browser diagnostic messages stay locally in
`build/browser-runtime.jsonl`.

The subsequent browser boot entered the original EXE at `00825330`, then
failed because InitializeCriticalSectionAndSpinCount was unresolved and
IsProcessorFeaturePresent had no registered stdcall signature. Both now have
real shims. The critical-section variant uses the existing recursive scheduler
lock; processor features match the guest CPUID rather than the modern host CPU.

`.venv/Scripts/python.exe verify_startup_win32.py` builds a focused suite through
the kit's build driver and runs the actual runtime/import dispatcher in Node.
It passed 403 checks including dynamic GetProcAddress, caller ESP/EIP,
last-error preservation, 24-byte object bounds, recursion, reacquisition and
feature queries. The new real game module also passed full V8 compilation.
The browser must run it again to verify that original-game startup proceeds.

The next actual browser attempt passed those startup imports and stopped at a
missing computed jump entry `00efb852`, from `00efb846` inside the dispatcher.
The active input is now `analysis/curated-core-q10-dispatcher`, which preserves
the q10 listings, exclusions and nonreturn contracts and adds seven audited
original-byte helper entries. The fresh strict translation has zero failures,
zero unmodelled instructions and zero table gaps. All seven helper pointers
are present in the generated dispatch table.

The integration rebuild uses
`.venv/Scripts/python.exe build.py --target web --regenerate --jobs 4 --diagnostic-all --background`.
`--diagnostic-all` retains backend register allocation while skipping expensive
LLVM IR passes for generated chunks; native runtime sources keep their normal
optimization. This build mode accelerates compilation but does not establish
playable performance. Publishing still requires successful full V8 compilation.
The old game configuration is saved in `game.toml.before-dispatcher-entries`.

The integration build finished successfully and passed full V8 compilation.
The published module is 147,013,816 bytes with at most 2,929 locals.
`analysis/dispatcher-browser-integration.json` records the observed failure and
the seven linked helper entries. Actual browser execution of this new build
and playable performance remain unverified.

The next browser attempt got beyond the dispatcher helpers and stopped at
`015102e0`, reached from `00507b10`. Original bytes at the missing target are
a 26-byte PUSH/PUSH/PUSH/PUSHFD/SUB/POPFD/RET trampoline. The interpreter now
executes PUSHFD/POPFD using the same flag helpers as translated code. It also
handles real-memory x87 loads, stores and arithmetic used by the initializer
callbacks that previously failed decoding. x87 comparisons, register forms
and other unsupported instructions are still rejected before execution.

`.venv/Scripts/python.exe verify_interp_wasm.py` runs the real interpreter's
268 checks in Wasm, covering metadata-stack transfers, flag restoration, both
floating widths, arithmetic direction, stack tags and refusal/budget cases.
Emscripten now keeps its Fault exception catch sites and link support enabled.
The incremental runtime rebuild and full V8 compilation succeeded. This
verifies that correction's code and tests, not the next browser/gameplay run.

The following actual browser run reached an access violation after several
missing calls were skipped by the inherited zero-result fallback. The missing
CRT SEH handler `00826794` also returned that fallback zero, which the runtime
mistook for ExceptionContinueExecution. Enabling that disposition alone would
not repair the missing execution or corrupted return chain.

The local player now sets `RECOMP_STRICT_UNKNOWN=1`: missing calls and failed
interpreted execution stop with a clear diagnostic before zero-result skipping.
Unknown-call diagnostics retain current guest bytes, important for image code
that the original dispatcher may modify. The startup Wasm suite still passes
403 checks and separately verifies that strict mode refuses an unsupported body.
The incremental real game rebuild and V8 compilation passed. Original-game
startup remains incomplete; these changes make the first missing routine
observable rather than treating a later corrupted return as its cause.

The next strict browser stop was the original startup constructor `014deef0`,
returning to `0046b2e8`. Its first 32 current guest bytes match the verified
original EXE. The interpreter rejects its memory DEC, and the complete body
also uses byte/word stores and external counter-reset branches. It is now an
explicit static translation seed in game.toml, rather than adding partial
interpreter handling. No exclusion or original-byte modification was added.

`audit_startup_014deef0.py` independently runs unchanged original instructions
in Unicorn with the witnessed caller registers and three synthetic counter
states. All three initialize 70 records, preserve callee registers, retain
object bounds and return with the correct ESP. This is a bounded reference,
not full original-game execution or a Wasm/browser verification. The strict
regeneration finished with zero failures, unmodelled instructions or table
gaps. The real game module linked, passed full V8 compilation, and contains
all five new function/continuation names. The loopback server serves the new
module with cache revalidation. Actual browser execution of this revision
and playable performance remain unverified.

## Verified browser gameplay (2026-10-21)

`docs/STATUS.md` carries the current evidence. The menu, the intro cinematic and
controllable gameplay all run in the browser: CJ walks through Los Santos under
held keyboard input. Run `target7d` (wasm `sha256 32630437…`, 266,386,779 bytes)
logged zero fixed-function refusals over 2316 s.

Still unverified: missions, vehicles, audible audio, save/load, stability beyond
about 35 minutes and usable performance. The measured rate is 0.3–0.5 FPS with
2.0–3.8 s frame times, so the build is interactive but not playable in real
time. Compilation, function counts and CPU-only tests do not establish any of
the browser results above; only the recorded runs do.
