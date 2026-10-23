"""Inventory main/audio imports against native registrations and DLL exports.

Finding a translated export is not an ABI or execution compatibility check.
"""
import hashlib
import json
from pathlib import Path
import sys

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools"))
import game_config
from imports_audit import TABLE


def main():
    cfg = game_config.load(ROOT)
    kit = ROOT / "vendor/recomp-kit"
    registrations = {}
    for directory in ("runtime", "dx"):
        for source in (kit / directory).rglob("*.cpp"):
            if "tests" in source.parts:
                continue
            for dll, name, handler in TABLE.findall(source.read_text(encoding="utf-8")):
                registrations.setdefault((dll.lower(), name), []).append(dict(handler=handler.strip(), source=str(source.relative_to(kit))))
    images = [(cfg["game"]["executable"], cfg["developer_exe_path"], cfg["game"]["sha256"])]
    exports = {}
    for module in cfg["aux_modules"]:
        images.append((module["name"], module["path"], module["sha256"]))
        data = module["path"].read_bytes()
        if hashlib.sha256(data).hexdigest() != module["sha256"]:
            raise ValueError("Configured DLL checksum differs")
        image = pefile.PE(data=data)
        exports[module["name"].lower()] = {s.name.decode() if s.name else f"#{s.ordinal}": s.address for s in image.DIRECTORY_ENTRY_EXPORT.symbols if not s.forwarder and s.address}
        exports[module["name"].lower()].update({f"#{s.ordinal}": s.address for s in image.DIRECTORY_ENTRY_EXPORT.symbols if not s.forwarder and s.address})
    entries = []
    for caller, binary, expected in images:
        data = binary.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Configured image checksum differs")
        for descriptor in pefile.PE(data=data).DIRECTORY_ENTRY_IMPORT:
            dll = descriptor.dll.decode()
            for symbol in descriptor.imports:
                name = symbol.name.decode() if symbol.name else f"#{symbol.ordinal}"
                handlers = registrations.get((dll.lower(), name), [])
                real = [h for h in handlers if h["handler"] not in ("nullptr", "NULL", "0")]
                module_export = exports.get(dll.lower(), {}).get(name)
                status = "auxiliary_export" if module_export is not None else "named_handler" if real else "registered_stub" if handlers else "not_found"
                entries.append(dict(caller=caller, dll=dll, symbol=name, status=status, export_rva=module_export, registrations=handlers))
    counts = {status: sum(e["status"] == status for e in entries) for status in ("auxiliary_export", "named_handler", "registered_stub", "not_found")}
    (ROOT / "analysis/all-module-imports.json").write_text(json.dumps(dict(compatibility_verified=False, counts=counts, entries=entries), indent=2), encoding="utf-8")
    print(counts)
    missing = sorted({(e["dll"], e["symbol"], e["status"]) for e in entries if e["status"] in ("not_found", "registered_stub")})
    for entry in missing:
        print(*entry)


if __name__ == "__main__":
    main()
