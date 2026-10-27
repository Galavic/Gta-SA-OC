"""Add verified original local stack-call prefixes to a separate input tree."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tomllib

import audit_local_call_thunks as A

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="analysis/curated-core-local")
    parser.add_argument("--checksum", action="store_true")
    parser.add_argument("--audit-file", type=Path, default=ROOT / "analysis/local-call-thunks.json")
    args = parser.parse_args()
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    binary = ROOT / cfg["game"]["developer_exe"]
    if hashlib.sha256(binary.read_bytes()).hexdigest() != cfg["game"]["sha256"]:
        raise ValueError("Original executable checksum differs")
    image = T.Image(str(binary))
    source = ROOT / cfg["translate"]["listings"]
    regions = cfg["translate"].get("data_regions", []) + json.loads((ROOT / cfg["translate"]["data_regions_file"]).read_text())
    image.declare_data_regions(regions)
    verified = A.audit(cfg, image, ROOT / "analysis/gta_sa.exe", checksum=args.checksum)
    checked = json.loads(args.audit_file.read_text())
    wasm = json.loads((ROOT / "build/local-thunk-wasm-status.json").read_text())
    if (checked != verified or wasm["original_executable_sha256"] != cfg["game"]["sha256"]
            or wasm["original_local_call_forms"] != len(checked["contracts"])
            or wasm.get("audit_report_sha256") != hashlib.sha256(args.audit_file.read_bytes()).hexdigest()
            or not wasm["registers_flags_pc_stack_identical"]):
        raise ValueError("Local prefixes lack matching original-byte and Wasm verification")
    out = ROOT / args.output
    if out.exists():
        raise ValueError("Use a fresh curation output directory")
    shutil.copytree(source, out)
    rows = (source / "functions.tsv").read_text(encoding="utf-8").splitlines()
    indexed = {int(line.split("\t")[0], 16): line.split("\t") for line in rows[1:]}
    calls = set(json.loads((ROOT / cfg["translate"]["no_fallthrough_calls_file"]).read_text()))
    data = {tuple(r) for r in json.loads((ROOT / cfg["translate"]["data_regions_file"]).read_text())}
    entries = {}
    for contract in checked["contracts"]:
        start, end = contract["callee"], contract["end"]
        if not 0 <= contract["changed_continuation"] - end <= 2:
            raise ValueError("Original continuation is outside the audited local form")
        instructions = image.recover(start, set(), bounds=(start, end))
        expected_count = contract.get("checksum_form", {}).get("canonical_instructions", 11)
        if len(instructions) != expected_count or not any(i.addr == contract["ret4"] and i.mnem == "RET" for i in instructions):
            raise ValueError("Original canonical prefix no longer has its exact JMP/RET4 exit")
        text = "\n".join(f"{i.addr:08x}  {i.mnem} {','.join(i.ops)}".rstrip() for i in instructions)+"\n"
        (out / "functions" / f"{start:08x}.asm").write_text(text, encoding="utf-8")
        if start not in indexed:
            indexed[start] = [f"{start:08x}", f"audited_local_stack_{start:08x}", str(end-start), "assembly", "original fixed CALL/RET4 prefix"]
        else:
            indexed[start][2] = str(end-start)
        calls.add(contract["call_site"])
        data.add((contract["metadata"], contract["metadata"]+4))
        entries[f"local_call_resume_{contract['changed_continuation']:08x}"] = contract["changed_continuation"]
        entries[f"local_call_target_{contract['destination']:08x}"] = contract["destination"]
    (out / "functions.tsv").write_text(rows[0]+"\n"+"\n".join("\t".join(indexed[a]) for a in sorted(indexed))+"\n", encoding="utf-8")
    (out / "nonreturning-calls.json").write_text(json.dumps(sorted(calls)), encoding="utf-8")
    (out / "inline-data.json").write_text(json.dumps(sorted(data)), encoding="utf-8")
    curated = T.read_curated(str(ROOT / cfg["translate"]["globals"]))
    curated.setdefault("entries", {}).update(entries)
    globals_text = "# Original local continuations/targets verified by local-call-thunks.json.\n"
    for section, values in curated.items():
        globals_text += f"\n[{section}]\n"
        for name, value in sorted(values.items()):
            globals_text += f"{name} = " + (f"0x{value:08x}" if isinstance(value,int) else json.dumps(value)) + "\n"
    (out / "globals.toml").write_text(globals_text, encoding="utf-8")
    (out / "local-call-thunks.json").write_text(json.dumps(checked, indent=2), encoding="utf-8")
    print(f"Prepared {len(checked['contracts'])} original local prefixes; {len(entries)} verified continuation/target names. Originals unchanged: {out}")


if __name__ == "__main__":
    main()
