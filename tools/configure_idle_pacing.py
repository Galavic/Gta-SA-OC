"""Raise gameplay pacing to 60 and remove the verified local Idle busy wait.

The executable and the global clock remain unchanged. Regenerate and rebuild
after applying; --restore reinstates the original translated comparison.
"""
import argparse
import hashlib
from pathlib import Path
import tomllib

import pefile

ROOT = Path(__file__).resolve().parents[1]
IMAGE_SHA = "a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26"
SITE = 0x0053E94A
LIMIT_SITE = 0x00619620
IDLE_PATCH = {"at": SITE, "text": "CMP EAX,0x0"}
LIMIT_PATCH = {"at": LIMIT_SITE, "text": "MOV dword ptr [0x00c1704c],0x3c"}
EXPECTED = [IDLE_PATCH, LIMIT_PATCH]
OLD_PATCH = 'instruction_patches = [{ at = 0x0053e94a, text = "CMP EAX,0x0" }]'
PATCH = ('instruction_patches = [{ at = 0x0053e94a, text = "CMP EAX,0x0" }, '
         '{ at = 0x00619620, text = "MOV dword ptr [0x00c1704c],0x3c" }]')
COMMENT = "# Verified gameplay pacing only; keep QPC and CTimer::Update at real time."
OLD_COMMENT = "# Verified Idle busy wait only; keep QPC and CTimer::Update at real time."


def configure(variant, restore=False):
    config_path = variant / "game.toml"
    text = config_path.read_text(encoding="utf-8")
    config = tomllib.loads(text)
    raw = (variant / config["game"]["developer_exe"]).read_bytes()
    if config["game"]["sha256"] != IMAGE_SHA or hashlib.sha256(raw).hexdigest() != IMAGE_SHA:
        raise ValueError("Idle patch requires the pinned single-player executable")
    pe = pefile.PE(data=raw, fast_load=True)
    offset = pe.get_offset_from_rva(SITE - pe.OPTIONAL_HEADER.ImageBase)
    # CMP EAX,14; JB backwards to the timer poll. Fail closed on other code.
    if raw[offset:offset + 5] != bytes.fromhex("83 f8 0e 72 e1"):
        raise ValueError("Idle comparison/branch differs from the verified executable")
    limit_offset = pe.get_offset_from_rva(LIMIT_SITE - pe.OPTIONAL_HEADER.ImageBase)
    if raw[limit_offset:limit_offset + 10] != bytes.fromhex("c7 05 4c 70 c1 00 1e 00 00 00"):
        raise ValueError("Frame-limit initialization differs from the verified executable")
    patches = config["translate"].get("instruction_patches", [])
    if patches and patches not in (EXPECTED, [IDLE_PATCH]):
        raise ValueError("Preserve unrelated instruction patches; review configuration manually")
    text = text.replace(OLD_COMMENT + "\n" + OLD_PATCH + "\n", "")
    if restore:
        text = text.replace(COMMENT + "\n" + PATCH + "\n", "")
    elif patches != EXPECTED:
        text = text.replace("[translate]\n", "[translate]\n" + COMMENT + "\n" + PATCH + "\n", 1)
    actual = tomllib.loads(text)["translate"].get("instruction_patches", [])
    if actual != ([] if restore else EXPECTED):
        raise ValueError("Could not safely update Idle pacing configuration")
    if text != config_path.read_text(encoding="utf-8"):
        temporary = config_path.with_suffix(".toml.new")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(config_path)
    return {"executable_sha256": IMAGE_SHA, "site": hex(SITE),
            "idle_wait_removed": not restore, "executable_modified": False,
            "gameplay_limit_fps": 30 if restore else 60,
            "clock_scaled": False, "browser_gameplay_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=ROOT / "variants/singleplayer")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    print(configure(args.game_dir, args.restore))
