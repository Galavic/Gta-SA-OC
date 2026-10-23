"""Generate an audited cumulative static startup module without rewriting base gen."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import uuid

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "vendor/recomp-kit"
BASE = ROOT / "build/recomp/gen"
MANIFEST = ROOT / "startup-addon-manifest.json"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def save(path, value):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def addresses(path):
    return {int(a, 16) for a in re.findall(r"^#define FIDX_([0-9a-f]{8}) ",
                                          path.read_text(), re.M)}


def call_returns(path):
    result = set()
    for array in re.findall(r"(?:const |static const )uint32_t \w*call_returns\[\] = \{(.*?)\};",
                            path.read_text(), re.S):
        result.update(int(a, 16) for a in re.findall(r"0x([0-9a-f]+)u", array))
    return result


def registered():
    entries = addresses(BASE / "funcs.h")
    returns = call_returns(BASE / "table.c")
    for module in BASE.glob("aux-*"):
        if module.name == "aux-startup":
            continue
        if (module / "funcs.h").exists():
            entries.update(addresses(module / "funcs.h"))
            returns.update(call_returns(module / "table.c"))
    return entries, returns


def prove(seed, proof, executable, expected_sha):
    import pefile
    evidence = json.loads(proof.read_text())
    if evidence.get("executable_sha256") != expected_sha:
        raise RuntimeError("Proof belongs to another original executable")
    case = next((c for c in evidence["cases"] if int(c.get("computed_target", "0"), 16) == seed), None)
    if not case or not case.get("current_prefix_matches_original") or not case.get("individual_emission_succeeded") or case.get("error"):
        raise RuntimeError(f"No admitted constructor proof for {seed:08x}")
    snapshot = Path(evidence["snapshot"])
    context = json.loads(snapshot.read_text())
    image_info = next(r for r in context["regions"] if r["suffix"] == ".image.bin" and r["written"])
    image = snapshot.with_name(snapshot.stem + ".image.bin")
    prefix = bytes.fromhex(case["current_prefix_hex"])
    pe = pefile.PE(str(executable), fast_load=True)
    offset = pe.get_offset_from_rva(seed - pe.OPTIONAL_HEADER.ImageBase)
    section = pe.get_section_by_rva(seed - pe.OPTIONAL_HEADER.ImageBase)
    if not section or not section.Characteristics & 0x20000000:
        raise RuntimeError(f"Seed {seed:08x} is outside executable sections")
    with executable.open("rb") as source:
        source.seek(offset)
        original = source.read(len(prefix))
    with image.open("rb") as source:
        source.seek(seed - image_info["base"])
        live = source.read(len(prefix))
    if not prefix or prefix != original or live != original:
        raise RuntimeError(f"Live/original/proof bytes disagree at {seed:08x}")
    return dict(address=f"{seed:08x}", proof=str(proof.resolve()), proof_sha256=digest(proof),
                snapshot=str(snapshot.resolve()), prefix_hex=prefix.hex())


def gate(stage, seeds, expected_sha):
    report = json.loads((stage / "report.json").read_text())
    for field in ["failures", "unmodelled", "table_gaps", "table_sites_undecoded"]:
        if report.get(field):
            raise RuntimeError(f"Strict addon report has {field}")
    if report.get("unmodelled_allowed") or report.get("table_gaps_allowed"):
        raise RuntimeError("Addon allowances are forbidden")
    symbols = json.loads((stage / "gen/symbols.json").read_text())
    if symbols["exe_sha256"] != expected_sha:
        raise RuntimeError("Translator used another executable")
    emitted = addresses(stage / "gen/funcs.h")
    alternates = {int(a, 16) for a in report["alternate_entries"]}
    # Overlapping seeds can merge into one carrier body with the rest kept
    # as alternate dispatch entries (e.g. loop fragments b1/b7 sharing bc's
    # body). Alternates are table-dispatched exactly like standalone
    # entries, so coverage -- not a raw body count -- is the sound rule.
    # functions_ok counts standalone bodies only; require every seed to be
    # standalone or alternate, and record the split for the admission.
    uncovered = seeds - emitted - alternates
    if uncovered:
        raise RuntimeError("Requested entries missing from module: " + ",".join(f"{a:08x}" for a in sorted(uncovered)))
    if report["functions_ok"] != len(emitted - alternates):
        # functions_ok counts standalone bodies: every emitted entry that
        # is not an alternate dispatch alias. The report and the table
        # must agree; any deviation means an unaccounted body slipped in.
        raise RuntimeError("Module does not contain exactly the requested function bodies")
    gate_coverage = dict(standalone_sorted=[f"{a:08x}" for a in sorted(seeds - alternates)],
                         alternate_sorted=[f"{a:08x}" for a in sorted(seeds & alternates)])
    if emitted != seeds | alternates or not seeds <= emitted:
        raise RuntimeError("Module dispatch table has unauthorized or missing entries")
    base_entries, base_returns = registered()
    module_range = re.search(r'"startup", 0x([0-9a-f]+)u, 0x([0-9a-f]+)u',
                             (stage / "gen/table.c").read_text())
    if not module_range:
        raise RuntimeError("Module registration range/name missing")
    low, high = (int(a, 16) for a in module_range.groups())
    for directory in BASE.glob("aux-*"):
        if directory.name == "aux-startup" or not (directory / "symbols.json").exists():
            continue
        auxiliary_base = int(json.loads((directory / "symbols.json").read_text())["image_base"], 16)
        if low <= auxiliary_base < high:
            raise RuntimeError("Another auxiliary registry range covers the main image: " + str(directory))

    overlap = emitted & base_entries
    if overlap:
        raise RuntimeError("Unprefixed fn_ADDR exports overlap base/aux: " + ",".join(f"{a:08x}" for a in sorted(overlap)))
    module_returns = call_returns(stage / "gen/table.c")
    externals = set()
    for source in (stage / "gen").glob("chunk_*.c"):
        text = source.read_text()
        externals.update(int(a, 16) for a in re.findall(r"recomp_(?:call|jump)\(c,\s*0x([0-9a-f]+)u?\)", text))
    missing = externals - base_entries - emitted - base_returns - module_returns
    padding_traps = set()
    if missing:
        # A fallthrough into INT3 padding traps in the original (breakpoint)
        # and aborts as an unknown jump in the recomp runtime. Both paths
        # stop loudly; neither continues silently. Allow such transfers only
        # when the pinned executable's first byte at the target is INT3, and
        # record every one of them in the admission.
        import pefile
        cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
        executable = ROOT / cfg["game"]["developer_exe"]
        pe = pefile.PE(str(executable), fast_load=True)
        with executable.open("rb") as source:
            image = source.read()
        for target in sorted(missing):
            rva = target - pe.OPTIONAL_HEADER.ImageBase
            try:
                first = image[pe.get_offset_from_rva(rva):][:1]
            except Exception:
                first = b""
            if first == b"\xcc":
                padding_traps.add(target)
        missing -= padding_traps
    if missing:
        raise RuntimeError("Unregistered literal module transfers: " + ",".join(f"{a:08x}" for a in sorted(missing)))
    return dict(strict_gate_passed=True, executable_sha256=expected_sha,
                requested_entries=[f"{a:08x}" for a in sorted(seeds)],
                seed_coverage=gate_coverage,
                emitted_entries=[f"{a:08x}" for a in sorted(emitted)],
                external_transfers=[f"{a:08x}" for a in sorted(externals)],
                padding_trap_transfers=[f"{a:08x}" for a in sorted(padding_traps)],
                base_header_sha256=digest(BASE / "funcs.h"),
                generated_files={p.name: digest(p) for p in (stage / "gen").iterdir() if p.is_file()},
                gameplay_verified=False, execution_verified=False)


def generate(args, previous):
    import tomllib
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    executable = ROOT / cfg["game"]["developer_exe"]
    expected_sha = cfg["game"]["sha256"]
    if digest(executable) != expected_sha:
        raise RuntimeError("Original executable hash mismatch")
    proofs = {int(c["address"], 16): c for c in previous.get("admitted_entries", [])}
    incoming = {int(a, 16) for a in args.entries}
    for seed in incoming:
        proofs[seed] = prove(seed, args.proof.resolve(), executable, expected_sha)
    for seed, record in proofs.items():
        proof = Path(record["proof"])
        if digest(proof) != record["proof_sha256"]:
            raise RuntimeError("Previously admitted proof changed")
        prove(seed, proof, executable, expected_sha)
    seeds = set(proofs)
    if not seeds:
        raise RuntimeError("No explicitly proven addon entries")
    stage_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    stage = ROOT / "build/startup-addon-stages" / stage_id
    stage.mkdir(parents=True, exist_ok=False)
    discovered = stage / "discovered.txt"
    discovered.write_text("# Explicit constructor proof seeds; independent captured-state evidence, not a full boot trace.\n" + "".join(f"{a:08x} call 00000000 1\n" for a in sorted(seeds)))
    command = [sys.executable, str(KIT / "tools/recomp/translate.py"), "--game", str(ROOT),
               "--out", str(stage / "gen"), "--as-module", "startup", "--discovered", str(discovered),
               "--report", str(stage / "report.json"), "--only"] + [f"{a:08x}" for a in sorted(seeds)]
    with (stage / "translation.log").open("w", encoding="utf-8") as log:
        subprocess.run(command, cwd=KIT, stdout=log, stderr=subprocess.STDOUT, check=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    admission = gate(stage, seeds, expected_sha)
    admission["admitted_entries"] = [proofs[a] for a in sorted(proofs)]
    admission["stage"] = str(stage)
    admission["translation_command"] = command
    admission["game_config_sha256"] = digest(ROOT / "game.toml")
    admission["translator_sha256"] = digest(KIT / "tools/recomp/translate.py")
    save(stage / "admission.json", admission)
    save(MANIFEST, admission)
    print("Audited generated stage:", stage)
    return stage


def publish_and_build(stage, args):
    # Publication/configuration must be invoked only after the current build
    # releases the CMake directory. Generation-only never touches this tree.
    status_path = ROOT / "build/web-status.json"
    if status_path.exists() and json.loads(status_path.read_text()).get("state") == "running":
        raise RuntimeError("Main web build is active; run --build-only after it finishes")
    if not stage.resolve().is_relative_to((ROOT / "build/startup-addon-stages").resolve()):
        raise RuntimeError("Publication requires a project-owned generated stage")
    admission = json.loads((stage / "admission.json").read_text())
    seeds = {int(a, 16) for a in admission["requested_entries"]}
    expected = gate(stage, seeds, admission["executable_sha256"])
    if expected["generated_files"] != admission["generated_files"]:
        raise RuntimeError("Generated addon files changed after admission")
    if digest(ROOT / "game.toml") != admission["game_config_sha256"]:
        raise RuntimeError("Game config changed after addon generation; regenerate the audited module")
    if digest(KIT / "tools/recomp/translate.py") != admission["translator_sha256"]:
        raise RuntimeError("Translator changed after addon generation; regenerate the audited module")
    destination = BASE / "aux-startup"
    # Never recursively delete: preserve every old aggregate outside gen/ so
    # CMake's aux-* glob can register exactly one same-image startup module.
    intended = BASE.resolve() / "aux-startup"
    if destination.resolve() != intended:
        raise RuntimeError("Addon destination is an unexpected link or path")
    if destination.exists():
        previous_files = {p.name: digest(p) for p in destination.iterdir() if p.is_file()}
        unchanged = previous_files == admission["generated_files"]
    else:
        unchanged = False
    if not unchanged:
        candidate = stage / ("publish-" + uuid.uuid4().hex)
        shutil.copytree(stage / "gen", candidate)
        backup = None
        if destination.exists():
            backup_root = ROOT / "build/startup-addon-backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = backup_root / uuid.uuid4().hex
            # Validate both resolved absolute move endpoints inside the
            # explicitly authorized project before moving a directory.
            if not destination.resolve().is_relative_to(ROOT.resolve()) or not backup.resolve().is_relative_to(ROOT.resolve()):
                raise RuntimeError("Addon backup move escapes project")
            destination.rename(backup)
        try:
            if not candidate.resolve().is_relative_to(ROOT.resolve()) or destination.resolve() != intended:
                raise RuntimeError("Addon publication move escapes expected paths")
            candidate.rename(destination)
        except Exception:
            if backup and not destination.exists():
                backup.rename(destination)
            raise

    sys.path.insert(0, str(KIT / "tools"))
    import build as driver
    sdk = Path.home() / "GTASAWebToolchains/emsdk"
    os.environ["EMSDK"] = str(sdk)
    os.environ["EM_CONFIG"] = str(sdk / ".emscripten")
    os.environ["PATH"] = str(ROOT / ".venv/Scripts") + os.pathsep + str(sdk / "upstream/emscripten") + os.pathsep + os.environ["PATH"]
    directory = ROOT / "build/cmake/web"
    driver.configure("web", driver.game_defines(ROOT, ROOT / "build") + ["-DRECOMP_GEN_DIAGNOSTIC_ALL=ON"], build_dir=directory)
    targets = list(dict.fromkeys(["recomp_gen_startup"] + args.targets))
    driver.build("web", targets, args.jobs, build_dir=directory)
    save(stage / "build-status.json", dict(build_succeeded=True, targets=targets,
                                          stage=str(stage), execution_verified=False, gameplay_verified=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--generate-only", action="store_true")
    mode.add_argument("--build-only", action="store_true")
    parser.add_argument("--entries", nargs="+", default=[], help="Explicit hexadecimal proven constructor addresses")
    parser.add_argument("--proof", type=Path, help="Original/current-byte batch admission evidence")
    parser.add_argument("--stage", type=Path, help="Previously admitted stage for --build-only")
    parser.add_argument("--targets", nargs="+", default=["game_boot_probe", "recomp_app"])
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    if args.generate_only:
        if args.entries and not args.proof:
            parser.error("Explicit new entries require --proof")
        generate(args, previous)
    else:
        stage = args.stage or (Path(previous["stage"]) if previous else None)
        if not stage or not (stage / "admission.json").exists():
            parser.error("--build-only requires a successfully admitted --stage")
        publish_and_build(stage.resolve(), args)


if __name__ == "__main__":
    main()
