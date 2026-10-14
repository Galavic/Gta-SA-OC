"""Recheck available failed original listings without pretending the game links.

Use the full previous strict build's blocker report as the baseline. This
diagnostic only checks emission of individual exported bodies; it does not
repeat discovery or prove that their callees have translated implementations.
"""
import json
import argparse
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parent
KIT = ROOT / "vendor/recomp-kit"
sys.path.insert(0, str(KIT / "tools/recomp/tests"))
from test_translate_insns import Opts
import translate as T


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "build/failed-function-probe")
    args = parser.parse_args()
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    T.configure(T.game_config.load(ROOT))
    source = args.baseline or ROOT / "build/recomp/translate-report.blockers.json"
    previous = json.loads(source.read_text(encoding="utf-8"))
    directory = args.input or ROOT / cfg["translate"]["listings"]
    rows = (directory / "functions.tsv").read_text(encoding="utf-8").splitlines()[1:]
    sizes = {int(row.split("\t")[0], 16): int(row.split("\t")[2]) for row in rows}
    entries = set(sizes) | {int(row["target"], 16) for row in previous["dangling_dispatch"]}
    image = T.Image(str(ROOT / cfg["game"]["developer_exe"]))
    regions = cfg["translate"].get("data_regions", []) + json.loads((directory / "inline-data.json").read_text())
    image.declare_data_regions(regions)
    image.noreturn_sites = frozenset(json.loads((directory / "nonreturning-calls.json").read_text()))
    T.RESUMABLE_STACKS = cfg["translate"]["resumable_stacks"]
    output = args.output
    output.mkdir(exist_ok=True)
    results = []
    for row in previous["failed_functions"]:
        address = int(row["address"], 16)
        listing = directory / "functions" / f"{address:08x}.asm"
        if not listing.is_file() or address not in sizes:
            results.append(dict(address=row["address"], state="no_exported_listing", previous_error=row["error"]))
            continue
        function = T.Function(address, "probe_" + row["address"], sizes[address], T.parse_listing(str(listing)))
        translator = T.Translator(image, entries, Opts())
        try:
            function.measure(image)
            translator.prepare(function)
            code = "\n".join(translator.translate(function))
            (output / f"{address:08x}.c").write_text(code, encoding="utf-8")
            results.append(dict(address=row["address"], state="emitted", previous_error=row["error"]))
        except T.TranslateError as error:
            results.append(dict(address=row["address"], state="failed", previous_error=row["error"], error=str(error)))
    report = dict(scope="Individual exported function emission only, no discovery or linked game",
                  game_execution_verified=False, results=results)
    (output / "status.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({state: sum(row["state"] == state for row in results) for state in ("emitted", "failed", "no_exported_listing")}))


if __name__ == "__main__":
    main()
