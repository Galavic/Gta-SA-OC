"""Identify embedded PE file buffers, keeping their bytes available as data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import tomllib
import pefile

ROOT = Path(__file__).resolve().parents[1]
variant = ROOT / "variants/singleplayer"
cfg = tomllib.loads((variant / "game.toml").read_text(encoding="utf-8"))
raw = (variant / cfg["game"]["developer_exe"]).read_bytes()
assert hashlib.sha256(raw).hexdigest() == cfg["game"]["sha256"]
parent = pefile.PE(data=raw, fast_load=True)
images = []
offset = 0
while True:
    offset = raw.find(b"MZ", offset + 1)
    if offset < 0:
        break
    try:
        child = pefile.PE(data=raw[offset:], fast_load=True)
    except pefile.PEFormatError:
        continue
    section = next((s for s in parent.sections if s.PointerToRawData <= offset <
                    s.PointerToRawData + s.SizeOfRawData), None)
    if section is None or not section.Characteristics & 0x40:
        continue
    extent = max([child.OPTIONAL_HEADER.SizeOfHeaders] +
                 [s.PointerToRawData + s.SizeOfRawData for s in child.sections if s.SizeOfRawData])
    if offset + extent > section.PointerToRawData + section.SizeOfRawData:
        continue
    address = parent.OPTIONAL_HEADER.ImageBase + parent.get_rva_from_offset(offset)
    images.append(dict(file_offset=offset, parent_address=address,
                       image_base=child.OPTIONAL_HEADER.ImageBase,
                       image_size=child.OPTIONAL_HEADER.SizeOfImage, raw_extent=extent))
regions = [[i["parent_address"], i["parent_address"] + i["raw_extent"]] for i in images]
assert not any(lo <= cfg["game"]["entry_point"] < hi for lo, hi in regions)
tables = []
for site, literal, count in [(0x014684be, 0x00411c38, 4), (0x0146a520, 0x00414379, 8),
                             (0x014a9c09, 0x00409503, 9), (0x014b17cf, 0x004116e8, 8)]:
    image = next(i for i in images if i["parent_address"] <= site <
                 i["parent_address"] + i["raw_extent"])
    child = pefile.PE(data=raw[image["file_offset"]:], fast_load=True)
    table_offset = child.get_offset_from_rva(literal - image["image_base"])
    targets = struct.unpack_from("<" + "I" * count, raw, image["file_offset"] + table_offset)
    assert all(any(image["image_base"] + s.VirtualAddress <= target <
                   image["image_base"] + s.VirtualAddress + s.Misc_VirtualSize and
                   s.Characteristics & 0x20000000 for s in child.sections) for target in targets)
    tables.append(dict(site=f"{site:08x}", child_table=f"{literal:08x}",
                       stored_table=f"{image['parent_address'] + table_offset:08x}",
                       child_targets=[f"{target:08x}" for target in targets]))
external_transfers = []
for listing in (variant / cfg["translate"]["listings"] / "functions").glob("*.asm"):
    for address, target in re.findall(r"(?m)^([0-9a-fA-F]{8})\s+(?:CALL|JMP|J[A-Z]+)\s+0x([0-9a-fA-F]+)", listing.read_text(encoding="utf-8")):
        address, target = int(address, 16), int(target, 16)
        if not any(lo <= address < hi for lo, hi in regions) and any(lo <= target < hi for lo, hi in regions):
            external_transfers.append([f"{address:08x}", f"{target:08x}"])
assert not external_transfers, external_transfers[:20]
report = dict(sha256=cfg["game"]["sha256"], original_bytes_modified=False,
              images=images, data_regions=regions, tables=tables,
              external_direct_transfers=external_transfers,
              scope="Stored PE files require separate loading and relocation if invoked; runtime compatibility unverified")
(variant / "embedded-images-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--apply", action="store_true")
if parser.parse_args().apply:
    path = variant / "game.toml"
    text = path.read_text(encoding="utf-8")
    marker = "data_regions_file = \"embedded-data-regions.json\""
    assert not cfg["translate"].get("data_regions_file") or cfg["translate"]["data_regions_file"] == "embedded-data-regions.json"
    (variant / "embedded-data-regions.json").write_text(json.dumps(regions, indent=2), encoding="utf-8")
    if marker not in text:
        text = text.replace("[translate]\n", "[translate]\n" + marker + "\n", 1)
        path.write_text(text, encoding="utf-8")
print(f"Verified {len(images)} embedded PE files, all four table blockers, and no external direct transfers.")
