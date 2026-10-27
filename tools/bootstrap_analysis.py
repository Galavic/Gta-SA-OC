"""Install pinned portable analysis tools without changing global PATH or Java."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(os.environ["LOCALAPPDATA"]) / "GTASAWebToolchains"
PACKAGES = {
    "ghidra": {
        "url": "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.3_build/ghidra_12.1.3_PUBLIC_20260817.zip",
        "sha256": "93a5d11a9ad510622acaaf908c556a7b9b764d338e78a7567f3689bf5081fd54",
        "directory": "ghidra_12.1.3_PUBLIC",
    },
    "jdk": {
        "url": "https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1%2B1/OpenJDK25U-jdk_x64_windows_hotspot_25.0.4.1_1.zip",
        "sha256": "00c847d804f4a78e9f04f2683faf14fed898535b177b7fc704486cb0284e9283",
        "directory": "jdk-25.0.4.1+1",
    },
}


def install(item):
    name, package = item
    archive = TOOLS / (name + ".zip")
    marker = TOOLS / (name + ".verified.json")
    target = TOOLS / package["directory"]
    if marker.exists() and target.is_dir():
        if json.loads(marker.read_text()) == package:
            print(f"{name}: already verified", flush=True)
            return name, str(target.resolve())
    if not archive.exists():
        print(f"{name}: downloading official pinned release", flush=True)
        partial = archive.with_suffix(".zip.part")
        with urllib.request.urlopen(package["url"], timeout=90) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        partial.replace(archive)
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != package["sha256"]:
        raise RuntimeError(f"{name}: SHA-256 mismatch; not extracting")
    print(f"{name}: checksum verified, extracting", flush=True)
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            destination = (TOOLS / entry.filename).resolve()
            if not destination.is_relative_to(TOOLS.resolve()):
                raise RuntimeError("Archive entry escapes tool directory")
        zipped.extractall(TOOLS)
    if not target.is_dir():
        raise RuntimeError(f"Missing extracted directory: {target}")
    marker.write_text(json.dumps(package, indent=2), encoding="utf-8")
    print(f"{name}: ready at {target}", flush=True)
    # Microsoft Store Python virtualizes AppData; external programs need the
    # canonical path instead of Python's virtual view of that directory.
    return name, str(target.resolve())


if __name__ == "__main__":
    TOOLS.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        paths = dict(pool.map(install, PACKAGES.items()))
    (ROOT / "analysis").mkdir(exist_ok=True)
    (ROOT / "analysis/toolchain.json").write_text(json.dumps(paths, indent=2), encoding="utf-8")
