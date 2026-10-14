"""Measure cold original-byte conversion, keeping public API as the reference."""
from pathlib import Path
import hashlib
import json
import statistics
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def public_conversion(image, ci):
    words = ci.mnemonic.split()
    rep = None
    if words[0] in image.REP_PREFIX:
        rep, words = image.REP_PREFIX[words[0]], words[1:]
    mnemonic = words[-1].upper()
    mnemonic = image.MNEM_ALIAS.get(mnemonic, mnemonic)
    operands = [image._op_text(ci, op, mnemonic) for op in ci.operands]
    if rep or mnemonic in T.Translator.STRING_MNEM:
        operands = []
    return mnemonic, rep, operands


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    binary = ROOT / cfg["game"]["developer_exe"]
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == cfg["game"]["sha256"]
    image = T.Image(str(binary))
    addresses = []
    for path in sorted((ROOT / cfg["translate"]["listings"] / "functions").glob("*.asm")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                addresses.append(int(line.split()[0], 16))
        if len(addresses) >= 6000:
            break
    addresses = sorted(set(addresses))[:6000]
    chunks = [(address, image.data[address-image.base:address-image.base+16]) for address in addresses]
    image.md.detail = True
    timings = {"public": [], "borrowed": []}
    signatures = {}
    for run in range(3):
        for name in (("public", "borrowed") if run % 2 == 0 else ("borrowed", "public")):
            rows = []
            start = time.perf_counter()
            for address, data in chunks:
                for ci in image.md.disasm(data, address, count=1):
                    try:
                        if name == "public":
                            result = public_conversion(image, ci)
                        else:
                            ins = image.to_insn(ci)
                            result = ins.mnem, ins.rep, ins.ops
                        rows.append((address, result))
                    except T.TranslateError as error:
                        rows.append((address, "error", str(error)))
            timings[name].append(time.perf_counter()-start)
            signatures[name] = hashlib.sha256(json.dumps(rows).encode()).hexdigest()
            if len(signatures) == 2:
                assert len(set(signatures.values())) == 1
    report = dict(instructions=len(chunks), passes=3, output_identical=True,
                  median_seconds={k: statistics.median(v) for k,v in timings.items()},
                  speedup=statistics.median(timings["public"])/statistics.median(timings["borrowed"]),
                  scope="Cold Capstone decoding/conversion sample, not full translation or gameplay", timings=timings)
    (ROOT / "build/operand-conversion-benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
