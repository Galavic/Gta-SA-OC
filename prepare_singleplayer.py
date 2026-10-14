"""Prepare and analyze this installation's GTA image in an isolated variant.

Installed files and the previous port stay untouched. The GTA PE is selected
by its verified identity from gta_sa.exe or the older patch_1.dat location.
The original audio library is stored as vorbisHooked.dll by the local loader.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pefile

ROOT = Path(__file__).resolve().parent
INSTALL = Path(os.environ.get("GTASA_GAME_DIR", str(Path.home() / "Downloads/GTA San Andreas/GTA San Andreas")))
VARIANT = ROOT / "variants/singleplayer"
IMAGE_SHA = "a559aa772fd136379155efa71f00c47aad34bbfeae6196b0fe1047d0645cbd26"
STATUS = VARIANT / "analysis-status.json"
ASSETS = ["anim", "audio", "data", "models", "movies", "text"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def prepare():
    source = next((candidate for candidate in (INSTALL / "gta_sa.exe", INSTALL / "patch_1.dat")
                   if candidate.is_file() and digest(candidate) == IMAGE_SHA), None)
    assert source is not None, "Installation has no executable matching the analyzed GTA image"
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == IMAGE_SHA, "Installation GTA image changed"
    pe = pefile.PE(data=raw)
    entry = pe.OPTIONAL_HEADER.ImageBase + pe.OPTIONAL_HEADER.AddressOfEntryPoint
    assert entry == 0x00824570 and pe.FILE_HEADER.Machine == 0x014c
    assert b"GTA: San Andreas" in raw
    for name in ASSETS:
        assert (INSTALL / name).is_dir(), "Missing GTA asset directory: " + name
    prepared = VARIANT / "prepared"
    analysis = VARIANT / "analysis"
    prepared.mkdir(parents=True, exist_ok=True)
    analysis.mkdir(exist_ok=True)
    image = prepared / "gta_sa.exe"
    if image.exists():
        assert digest(image) == IMAGE_SHA, "Preserve a different existing variant image"
    else:
        shutil.copy2(source, image)
    metadata = json.loads((ROOT / "build/relocated-audio/preparation.json").read_text())
    modules = []
    for module in metadata["modules"]:
        name = module["name"]
        installed_name = "vorbisHooked.dll" if name == "vorbisFile.dll" else name
        assert digest(INSTALL / installed_name) == module["original_sha256"], "Audio identity mismatch"
        staged_source = ROOT / "prepared" / name
        assert digest(staged_source) == module["prepared_sha256"]
        destination = prepared / name
        if destination.exists():
            assert digest(destination) == module["prepared_sha256"]
        else:
            shutil.copy2(staged_source, destination)
        # Existing listings describe these exact unchanged rebased bytes.
        modules.append(dict(module, source_name=installed_name,
                            listings=str(ROOT / "analysis" / name)))
    stream = INSTALL / "stream.ini"
    if stream.is_file():
        shutil.copy2(stream, prepared / stream.name)
    globals_file = analysis / "globals.toml"
    if not globals_file.exists():
        globals_file.write_text("# No guessed single-player globals or hooks.\n", encoding="utf-8")
    config = f'''# Isolated GTA image from this installation; gameplay not verified.
[game]
id = "gtasa-singleplayer"
name = "Grand Theft Auto: San Andreas"
app_name = "GTASASingleplayer"
bundle_id = "local.gtasa.singleplayer"
executable = "gta_sa.exe"
sha256 = "{IMAGE_SHA}"
image_base = 0x00400000
entry_point = 0x{entry:08x}
heap_base = 0x02500000
guest_size = 0x20000000
guest_root = 'C:\\GTASA'
developer_exe = "prepared/gta_sa.exe"
windows_version = "5.1"

[translate]
listings = "analysis/gta_sa.exe"
globals = "analysis/globals.toml"
entry_points = [0x{entry:08x}]
animation_counter = 0
volatile_reads = []
resumable_stacks = true
legacy_address_intrinsics = false

[setup]
required_dirs = ["models", "data", "audio", "anim"]
[controls]
default_layout = "hidden"
pad = "off"
[hooks]
cursor_surface_ptrs = []
[mods]
builtin = "none"
'''
    for module in modules:
        key = Path(module["name"]).stem.lower()
        config += f'''\n[modules.aux.{key}]
name = "{module['name']}"
path = "prepared/{module['name']}"
sha256 = "{module['prepared_sha256']}"
base = {module['base']}
size = {module['size']}
listings = {json.dumps(module['listings'])}
function_alignment = 4
'''
    config_path = VARIANT / "game.toml"
    if config_path.exists():
        assert config_path.read_text(encoding="utf-8") == config, "Preserve edited variant configuration"
    else:
        config_path.write_text(config, encoding="utf-8")
    report = dict(installation=str(INSTALL), source_image=str(source), source_sha256=IMAGE_SHA,
                  staged_image=str(image), entry=f"{entry:08x}", original_files_modified=False,
                  previous_port_modified=False, included_asset_directories=ASSETS,
                  reused_audio_modules=modules,
                  excluded_loaders=["installed gta_sa.exe (Git LFS metadata)", "DINPUT8.DLL",
                                    "installed vorbisFile.dll loader", "scripts", "patch_0.dat", "SA-MP files"],
                  unmodified_retail_version_verified=False, gameplay_verified=False)
    save(VARIANT / "preparation.json", report)
    print("Prepared unchanged GTA PE:", image, "entry:", hex(entry), flush=True)


def analyze():
    toolchain = json.loads((ROOT / "analysis/toolchain.json").read_text())
    ghidra = Path(toolchain["ghidra"])
    jdk = Path(toolchain["jdk"])
    assert (ghidra / "support/analyzeHeadless.bat").is_file()
    assert (jdk / "bin/java.exe").is_file()
    projects = VARIANT / "analysis/ghidra-project"
    projects.mkdir(exist_ok=True)
    state = dict(state="analyzing", pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
                 variant=str(VARIANT), executable_sha256=IMAGE_SHA, gameplay_verified=False)
    save(STATUS, state)
    env = dict(os.environ, JAVA_HOME=str(jdk))
    env["PATH"] = str(jdk / "bin") + os.pathsep + env["PATH"]
    command = ["cmd.exe", "/c", str(ghidra / "support/analyzeHeadless.bat"), str(projects),
               "GTA_Singleplayer", "-import", str(VARIANT / "prepared/gta_sa.exe"),
               "-scriptPath", str(ROOT / "tools"), "-preScript", "ConfigureAssemblyAnalysis.java",
               "-postScript", "ExportAssembly.java", str(VARIANT / "analysis"), "-max-cpu", "4"]
    state["analysis_command"] = command
    save(STATUS, state)
    try:
        subprocess.run(command, cwd=VARIANT, env=env, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        summary = json.loads((VARIANT / "analysis/gta_sa.exe/assembly-summary.json").read_text())
        assert summary["functions"] > 0 and summary["instructions"] > 0
        state.update(state="translating", analysis_summary=summary)
        save(STATUS, state)
        output = VARIANT / "build/recomp"
        output.mkdir(parents=True, exist_ok=True)
        translate = [sys.executable, str(ROOT / "vendor/recomp-kit/tools/recomp/translate.py"),
                     "--game", str(VARIANT), "--out", str(output / "gen"),
                     "--report", str(output / "translate-report.json")]
        state["translation_command"] = translate
        save(STATUS, state)
        subprocess.run(translate, cwd=ROOT / "vendor/recomp-kit", check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        state["state"] = "translated_unbuilt"
    except Exception as error:
        state.update(state="needs_review", error=str(error))
        print("Analysis/translation requires review:", error, flush=True)
    finally:
        state["updated_utc"] = datetime.now(timezone.utc).isoformat()
        save(STATUS, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--analyze", action="store_true")
    mode.add_argument("--background", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.analyze:
        analyze()
    else:
        assert (VARIANT / "preparation.json").exists()
        with (VARIANT / "analysis.log").open("a", encoding="utf-8") as log:
            child = subprocess.Popen([str(ROOT / ".venv/Scripts/python.exe"), str(Path(__file__).resolve()),
                                      "--analyze"], cwd=ROOT, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW |
                                                   subprocess.CREATE_NEW_PROCESS_GROUP |
                                                   subprocess.CREATE_BREAKAWAY_FROM_JOB)
        print("Single-player analysis supervisor PID", child.pid)


if __name__ == "__main__":
    main()
