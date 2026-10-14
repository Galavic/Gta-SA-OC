# Runtime changes

`current-vendor.patch` is the complete local source diff against the revision
in `recomp-kit-base.txt`, including new handwritten files. The submodule is
pinned to the same revision. Apply this patch once to a clean submodule.

`recovery-cache.patch` and `declared-data-recovery.patch` are historical partial
patches. Do not apply them together with the complete patch.

To reproduce a source snapshot after local dependency edits, run
`python tools/snapshot_runtime_patch.py`. It does not modify the dependency's
index and rejects unexpected untracked file types.

The handwritten recomp-kit implementation uses its upstream MIT license,
preserved in `RECOMP_KIT_LICENSE`. Original game materials remain excluded.
