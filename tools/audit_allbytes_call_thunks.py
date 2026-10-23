"""Scan every executable byte for the audited local CALL/RET4 thunk forms.

The listing-only audit missed a checksum thunk call inside a function whose
Ghidra listing diverged at an anti-debug decoy.  A real CALL is an E8 byte at
an instruction boundary; the thunk recognizers prove the target form from the
original bytes, so scanning executable sections finds call sites independently
of listing coverage.  Declared data regions are excluded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=ROOT / "variants/singleplayer")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    game = args.game_dir.resolve()
    sys.path.insert(0, str(game.parent.parent / "vendor/recomp-kit/tools/recomp"))
    sys.path.insert(0, str(ROOT))
    import translate as T
    import audit_local_call_thunks as fixed
    import audit_checksum_call_thunks as checksum

    cfg = tomllib.loads((game / "game.toml").read_text(encoding="utf-8"))
    binary = game / cfg["game"]["developer_exe"]
    if hashlib.sha256(binary.read_bytes()).hexdigest() != cfg["game"]["sha256"]:
        raise SystemExit("original executable checksum differs")
    image = T.Image(str(binary))
    regions = list(cfg["translate"].get("data_regions", []))
    data_file = cfg["translate"].get("data_regions_file")
    if data_file:
        regions += json.loads((game / data_file).read_text(encoding="utf-8"))
    image.declare_data_regions(regions)

    def at_site(site, target):
        if not (image.base <= site and site + 5 <= image.end
                and image.data[site - image.base] == 0xe8
                and image.is_exec(target) and not image.is_declared_data(site)
                and not image.is_declared_data(target)):
            return None
        rel = int.from_bytes(image.data[site - image.base + 1:site - image.base + 5],
                             "little", signed=True)
        if (site + 5 + rel) & 0xffffffff != target:
            return None
        # Cheap prefix check before the full recognizer: every audited form
        # starts by adding an immediate to the return word at [esp].
        head = image.data[target - image.base:target - image.base + 3]
        if head not in (bytes.fromhex("83 04 24"), bytes.fromhex("81 04 24")):
            return None
        contract = fixed.inspect(image, site, target)
        if contract is None:
            contract = checksum.inspect(image, site, target)
        if contract is not None and contract.get("checksum_form") is None:
            contract["form"] = "fixed"
        elif contract is not None:
            contract["form"] = "checksum"
        return contract

    found = {}

    # Keep every listing-proven contract even if this byte scan happens to
    # miss it (for example because a listing CALL was patched in memory).
    listing_dir = game / cfg["translate"]["listings"]
    listing_sites = set()
    for file in sorted((listing_dir / "functions").glob("*.asm")):
        for match in re.finditer(r"^([0-9a-fA-F]+)\s+CALL 0x([0-9a-fA-F]+)\s*$",
                                 file.read_text(encoding="utf-8"), re.M):
            site, target = int(match[1], 16), int(match[2], 16)
            if site in found:
                continue
            listing_sites.add(site)
            contract = at_site(site, target)
            if contract is not None:
                contract["provenance"] = "listing"
                found[site] = contract

    scanned = 0
    for lo, hi, name in image.exec_ranges:
        if name in (".reloc", ".rsrc"):
            continue
        start, end = lo - image.base, hi - image.base
        cursor = start
        while True:
            off = image.data.find(b"\xe8", cursor, end)
            if off < 0:
                break
            cursor = off + 1
            site = image.base + off
            if site in found or image.is_declared_data(site):
                continue
            rel = int.from_bytes(image.data[off + 1:off + 5], "little", signed=True)
            target = (site + 5 + rel) & 0xffffffff
            scanned += 1
            contract = at_site(site, target)
            if contract is not None:
                contract["provenance"] = "bytes"
                found[site] = contract

    output = args.output or (game / "analysis/local-call-thunks-allbytes.json")
    report = dict(
        executable_sha256=cfg["game"]["sha256"],
        original_bytes_modified=False,
        raw_export_modified=False,
        scope=("Every E8 in executable sections plus listing CALLs; target form and "
               "RET4 continuation proven from original bytes"),
        scanned_e8_sites=scanned,
        contracts=[found[k] for k in sorted(found)],
    )
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    new = [c for c in report["contracts"]
           if c["provenance"] == "bytes" and c["call_site"] not in listing_sites]
    print("scanned %d E8 sites; verified %d contracts (%d fixed, %d checksum), "
          "%d found by byte scan" % (
              scanned, len(report["contracts"]),
              sum(c["form"] == "fixed" for c in report["contracts"]),
              sum(c["form"] == "checksum" for c in report["contracts"]), len(new)))
    for c in new:
        print("  + %08x -> %08x  cont %08x  dest %08x" % (
            c["call_site"], c["callee"], c["changed_continuation"], c["destination"]))


if __name__ == "__main__":
    main()
