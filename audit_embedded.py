"""Validate stored PE buffers without changing the original executable."""
import hashlib
import json
from pathlib import Path
import struct
import tomllib

import pefile

ROOT = Path(__file__).resolve().parent


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    raw = (ROOT / cfg["game"]["developer_exe"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != cfg["game"]["sha256"]:
        raise ValueError("Original executable checksum differs")
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
        section = next((s for s in parent.sections if s.PointerToRawData <= offset < s.PointerToRawData + s.SizeOfRawData), None)
        if section is None or not section.Characteristics & 0x40:
            continue
        extent = max([child.OPTIONAL_HEADER.SizeOfHeaders] + [s.PointerToRawData + s.SizeOfRawData for s in child.sections if s.SizeOfRawData])
        if offset + extent > section.PointerToRawData + section.SizeOfRawData:
            continue
        address = parent.OPTIONAL_HEADER.ImageBase + parent.get_rva_from_offset(offset)
        images.append(dict(file_offset=offset, parent_address=address, image_base=child.OPTIONAL_HEADER.ImageBase, image_size=child.OPTIONAL_HEADER.SizeOfImage, raw_extent=extent))
    regions = [[i["parent_address"], i["parent_address"] + i["raw_extent"]] for i in images]
    if regions != cfg["translate"]["data_regions"]:
        raise ValueError("Stored PE extents differ from declared data regions")
    tables = []
    for site, literal, count in [(0x0135D82C, 0x00415AFD, 8), (0x0139D4F9, 0x00408FB3, 9)]:
        image = next(i for i in images if i["parent_address"] <= site < i["parent_address"] + i["raw_extent"])
        child = pefile.PE(data=raw[image["file_offset"]:], fast_load=True)
        table_offset = child.get_offset_from_rva(literal - image["image_base"])
        targets = struct.unpack_from("<" + "I" * count, raw, image["file_offset"] + table_offset)
        if not all(image["image_base"] <= t < image["image_base"] + image["image_size"] for t in targets):
            raise ValueError("Embedded jump table contains an out-of-image target")
        tables.append(dict(site=hex(site), stored_table=hex(image["parent_address"] + table_offset), targets=[hex(t) for t in targets]))
    report = dict(sha256=cfg["game"]["sha256"], bytes_modified=False, images=images, tables=tables, scope="Stored programs require separate loading and relocation if invoked; this audit does not establish runtime compatibility.")
    (ROOT / "analysis/embedded-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Validated {len(images)} stored PE buffers and {len(tables)} embedded jump tables; original bytes unchanged.")


if __name__ == "__main__":
    main()
