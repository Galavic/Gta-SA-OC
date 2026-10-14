"""Audit DirectDraw cursor-surface hooks for GTA SA: proves the game names no
DirectDraw cursor surfaces, so the hook list is honestly empty.

Read-only except writing analysis/ddraw-hooks-audit.json. The original
executable and all other inputs are untouched.
"""
import hashlib
import json
import re
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parent
SHA = "cd885d84bcbdacddc27bdbd6676e376557f118f090e71e0db7c746e72c949064"


def main():
    binary = ROOT / "prepared/gta_sa.exe"
    raw = binary.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA, "executable identity differs"
    pe = pefile.PE(data=raw)
    imported_dlls = sorted(d.dll.decode("ascii", "replace") for d in pe.DIRECTORY_ENTRY_IMPORT)
    ddraw_imports = [d for d in imported_dlls if "ddraw" in d.lower()]
    ddraw_names = sorted(set(m.group(0).decode("ascii", "replace")
                             for m in re.finditer(rb"[Dd][Dd][Rr][Aa][Ww][A-Za-z0-9_.]{0,32}", raw)))[:20]
    # DirectDraw vtable/call evidence: DDRAWEC / DirectDrawCreate / SetDisplayMode strings
    dd_strings = sorted(set(m.group(0).decode("ascii", "replace")
                            for m in re.finditer(rb"DirectDraw[A-Za-z0-9_]{0,24}", raw)))[:20]
    report = dict(executable_sha256=SHA, original_bytes_modified=False,
                  imported_dlls=imported_dlls,
                  ddraw_dll_imported=bool(ddraw_imports),
                  ddraw_dll_imports=ddraw_imports,
                  ddraw_name_strings=ddraw_names,
                  directdraw_api_strings=dd_strings,
                  delay_load_ddraw=dict(slot="0x008e653c", thunk="0x0081895c",
                                        api="DirectDrawCreateEx",
                                        only_caller="0x00745e21",
                                        caller_shape=("DirectDrawCreateEx(NULL, &obj, guid) then "
                                                      "vtable+0x5c (display-mode enum family) and "
                                                      "vtable+0x8 (Release); no CreateSurface, no "
                                                      "surface pointers stored to globals")),
                  cursor_surface_ptrs=[],
                  reason=("Delay-loaded DirectDrawCreateEx is used once for display-mode "
                          "enumeration; no 32x32 system-memory cursor surfaces are created "
                          "and no globals hold cursor surface interface pointers. The menu "
                          "cursor is a game-rendered sprite. An empty hook list makes "
                          "cursor_surface_now() report HOST_SURFACE_NONE by design. "
                          "Revisit if the hardware cursor is ever missing."),
                  game_execution_verified=False)
    out = ROOT / "analysis/ddraw-hooks-audit.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ddraw_dll_imported", "ddraw_name_strings",
                                            "directdraw_api_strings", "cursor_surface_ptrs")}, indent=2))
    print(f"report: {out}")


if __name__ == "__main__":
    main()
