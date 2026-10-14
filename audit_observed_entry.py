"""Admit a decoder-refused entry witnessed by the original Wasm boot probe.

This verifies captured bytes and isolated translation, not execution of the
new body. The cumulative module's separate gate checks dispatch coverage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pefile
import capstone

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools"))
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import game_config
import translate as T


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    snapshot = args.snapshot.resolve()
    state = json.loads(snapshot.read_text())
    target = state["target"]
    cfg = game_config.load(str(ROOT))
    T.configure(cfg)
    executable = ROOT / "prepared/gta_sa.exe"
    original = executable.read_bytes()
    sha = hashlib.sha256(original).hexdigest()
    assert sha == state["exe_sha256"]
    pe = pefile.PE(data=original)
    section = pe.get_section_by_rva(target - pe.OPTIONAL_HEADER.ImageBase)
    assert section and section.Characteristics & 0x20000000
    region = next(r for r in state["regions"] if r["suffix"] == ".image.bin")
    assert region["written"]
    live = snapshot.with_name(snapshot.stem + ".image.bin").read_bytes()
    offset = pe.get_offset_from_rva(target - pe.OPTIONAL_HEADER.ImageBase)
    prefix = live[target - region["base"]:target - region["base"] + 32]
    assert len(prefix) == 32 and prefix == original[offset:offset + 32]
    known = set()
    for header in [ROOT / "build/recomp/gen/funcs.h", *list((ROOT / "build/recomp/gen").glob("aux-*/funcs.h"))]:
        known.update(int(a, 16) for a in re.findall(r"^#define FIDX_([0-9a-f]{8}) ", header.read_text(), re.M))
    assert target not in known, "Observed target already has a dispatch entry"
    image = T.Image(str(executable))
    instructions = image.recover(target, known, limit=4096)
    assert instructions, "Original body did not recover"
    # Validate every admitted instruction against the dumped live image,
    # including noncontiguous branches, rather than only its entry prefix.
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for instruction in instructions:
        at = instruction.addr
        off = pe.get_offset_from_rva(at - pe.OPTIONAL_HEADER.ImageBase)
        decoded = next(decoder.disasm(original[off:off+15], at, count=1))
        assert live[at-region["base"]:at-region["base"]+decoded.size] == original[off:off+decoded.size]
    function = T.Function(target, "observed_boot_entry", 1, instructions)
    function.measure(image)
    translator = T.Translator(image, known | {target}, SimpleNamespace(eager_flags=False))
    translator.all_insn_addrs = known | function.addrs
    translator.prepare(function)
    translator.translate(function)
    assert not translator.unmodelled
    case = dict(computed_target=f"{target:08x}", current_prefix_hex=prefix.hex(),
                current_prefix_matches_original=True, individual_emission_succeeded=True,
                recovered_instructions=len(instructions), all_recovered_live_bytes_match=True,
                source_eip=f"{state['eip']:08x}", error=None,
                evidence_kind="real Wasm boot decoder-refusal snapshot")
    report = dict(executable_sha256=sha, snapshot=str(snapshot), cases=[case],
                  execution_verified=False, gameplay_verified=False,
                  limitation="Captured original instruction bytes and isolated emission; cumulative translation and execution still required.")
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(case, indent=2))


if __name__ == "__main__":
    main()
