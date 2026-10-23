"""Create verified, independently rebased audio DLL copies for translation.

The installed game is read-only. This preparation does not implement missing
audio APIs or prove that the resulting modules execute correctly.
"""
import hashlib
import json
from pathlib import Path
import struct
import tomllib

import pefile

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rebase(raw, base):
    image = pefile.PE(data=raw)
    previous = image.OPTIONAL_HEADER.ImageBase
    entries = [e for b in getattr(image, "DIRECTORY_ENTRY_BASERELOC", []) for e in b.entries]
    if base != previous and not entries:
        raise ValueError("Module has no relocation directory")
    if any(e.type not in (0, 3) for e in entries):
        raise ValueError("Only ABSOLUTE and HIGHLOW PE32 relocations are supported")
    offsets = [image.get_offset_from_rva(e.rva) for e in entries if e.type == 3]
    if len(offsets) != len(set(offsets)):
        raise ValueError("Duplicate relocation targets")
    original_words = [(o, struct.unpack_from("<I", raw, o)[0]) for o in offsets]
    delta = base - previous
    # Work on the exact file bytes: reserializing parsed import structures can
    # rewrite a bound IAT even when the requested base did not change.
    output = bytearray(raw)
    for offset, value in original_words:
        struct.pack_into("<I", output, offset, (value + delta) & 0xFFFFFFFF)
    base_offset = image.OPTIONAL_HEADER.get_field_absolute_offset("ImageBase")
    checksum_offset = image.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    struct.pack_into("<I", output, base_offset, base)
    checksum = pefile.PE(data=bytes(output)).generate_checksum()
    struct.pack_into("<I", output, checksum_offset, checksum)
    output = bytes(output)
    for offset, value in original_words:
        if struct.unpack_from("<I", output, offset)[0] != (value + delta) & 0xFFFFFFFF:
            raise ValueError("Relocation did not preserve the declared address offset")
    # Accept changes only at the declared relocations and PE base/checksum fields.
    allowed = bytearray(len(raw))
    for offset in offsets + [image.OPTIONAL_HEADER.get_field_absolute_offset("ImageBase"), image.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")]:
        allowed[offset:offset + 4] = b"\1" * 4
    if len(output) != len(raw) or any(a != b and not allowed[i] for i, (a, b) in enumerate(zip(raw, output))):
        raise ValueError("Unexpected bytes changed during rebasing")
    check = pefile.PE(data=output)
    if check.OPTIONAL_HEADER.ImageBase != base:
        raise ValueError("Rebased PE header differs")
    return output, len(offsets), check.OPTIONAL_HEADER.SizeOfImage


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    # Always source the immutable installation, even after game.toml selects
    # the staged installation containing our rebased copies.
    install = ROOT / "original"
    if sha((install / "gta_sa.exe").read_bytes()) != cfg["game"]["sha256"]:
        raise ValueError("Original executable checksum differs")
    inventory = tomllib.loads((ROOT / "audio_modules.toml").read_text())["modules"]
    destination = ROOT / "build/relocated-audio"
    destination.mkdir(parents=True, exist_ok=True)
    reports, config = [], ["# Generated preparation; not activated in game.toml.", "# Requires a 512 MiB guest arena and staged installation with these DLLs."]
    for source in inventory:
        name = source["name"]
        raw = (install / name).read_bytes()
        if sha(raw) != source["sha256"]:
            raise ValueError(f"Original {name} checksum differs")
        base = source["load_base"]
        output, count, size = rebase(raw, base)
        (destination / name).write_bytes(output)
        if sha((install / name).read_bytes()) != source["sha256"]:
            raise ValueError("Original DLL unexpectedly changed")
        key = Path(name).stem.lower()
        reports.append(dict(name=name, original_sha256=source["sha256"], prepared_sha256=sha(output), base=hex(base), size=hex(size), validated_relocations=count))
        config.extend([f"\n[modules.aux.{key}]", f'name = "{name}"', f'path = "build/relocated-audio/{name}"', f'sha256 = "{sha(output)}"', f"base = 0x{base:08x}", f"size = 0x{size:x}", f'listings = "analysis/{name}"', "function_alignment = 4"])
    (destination / "modules.toml").write_text("\n".join(config) + "\n", encoding="utf-8")
    (destination / "preparation.json").write_text(json.dumps(dict(originals_modified=False, runtime_verified=False, modules=reports), indent=2), encoding="utf-8")
    print(f"Prepared {len(reports)} separate DLL images; validated {sum(r['validated_relocations'] for r in reports)} relocation words. Original files unchanged.")


if __name__ == "__main__":
    main()
