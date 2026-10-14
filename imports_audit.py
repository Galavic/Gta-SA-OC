"""Compare original import names with runtime registration tables.

Text matching only: an implemented registration is not a compatibility test.
Dynamic LoadLibrary/GetProcAddress and COM methods are outside this inventory.
"""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
TABLE = re.compile(r'\{\s*"([^"\n]+\.dll)"\s*,\s*"([^"\n]+)"\s*,\s*\d+\s*,\s*([^}\n]+)\}', re.I)


if __name__ == "__main__":
    registrations = {}
    kit = ROOT / "vendor/recomp-kit"
    for directory in ("runtime", "dx"):
        for source in (kit / directory).rglob("*.cpp"):
            if "tests" in source.parts:
                continue
            for dll, name, handler in TABLE.findall(source.read_text(encoding="utf-8")):
                registrations.setdefault((dll.lower(), name), []).append({
                    "handler": handler.strip(), "source": str(source.relative_to(kit)),
                })
    original = json.loads((ROOT / "analysis/pe.json").read_text())
    entries = []
    for entry in original["imports"]:
        name = entry["name"]
        # This name was obtained from the supplied DLL's export table.
        if entry["dll"].lower() == "eax.dll" and entry["ordinal"] == 6:
            name = "EAXDirectSoundCreate8"
        candidates = registrations.get((entry["dll"].lower(), name), [])
        implemented = [c for c in candidates if c["handler"] not in ("nullptr", "NULL", "0")]
        status = "named_handler" if implemented else "registered_stub" if candidates else "not_found"
        entries.append({**entry, "resolved_name": name, "status": status, "registrations": candidates})
    report = {
        "kind": "static_registration_inventory_only", "compatibility_verified": False,
        "total_imports": len(entries),
        "counts": {status: sum(e["status"] == status for e in entries)
                   for status in ("named_handler", "registered_stub", "not_found")},
        "entries": entries,
    }
    (ROOT / "analysis/imports-coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(report["counts"])
    for entry in entries:
        if entry["status"] != "named_handler":
            print(entry["dll"], entry["resolved_name"] or f"ordinal {entry['ordinal']}", entry["status"])
