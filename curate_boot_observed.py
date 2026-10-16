"""Curate one boot-probe-observed indirect target as a dispatcher helper.

Same verification bar as curate_dispatcher_helpers.py (original bytes,
bounded recovery, capstone identity, C emission), but the execution evidence
is the translated boot probe reaching the transfer, not a synthetic Unicorn
probe. Additive into a fresh tree; existing inputs untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import capstone as C

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor/recomp-kit/tools/recomp/tests'))
from test_translate_insns import Opts
import translate as T


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, help='hex, e.g. 00efeaab')
    parser.add_argument('--from-addr', required=True, help='hex transfer site, e.g. 00efe1b1')
    parser.add_argument('--evidence', required=True, help='probe stderr excerpt file proving the transfer')
    parser.add_argument('--input', default='analysis/curated-core-q10-dispatcher')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    target = int(args.target, 16)
    from_addr = int(args.from_addr, 16)
    cfg = __import__('tomllib').loads((ROOT / 'game.toml').read_text(encoding='utf-8'))
    T.configure(T.game_config.load(ROOT))
    source = ROOT / args.input
    out = ROOT / args.output
    if out.exists():
        raise ValueError('Use a fresh output directory')
    binary = ROOT / cfg['game']['developer_exe']
    exe_sha = digest(binary)
    if exe_sha != cfg['game']['sha256']:
        raise ValueError('Original executable SHA differs')
    raw_evidence = Path(args.evidence).read_bytes()
    evidence = None
    for encoding in ('utf-8', 'utf-16', 'utf-8-sig'):
        try:
            evidence = raw_evidence.decode(encoding)
            if f'{target:08x}' in evidence.lower():
                break
        except (UnicodeDecodeError, ValueError):
            continue
    if evidence is None:
        raise ValueError('evidence file is not decodable text')
    assert f'{target:08x}' in evidence.lower().replace('0x', '') or f'{target:08x}' in evidence, \
        'evidence does not name the target'
    assert f'{from_addr:08x}' in evidence.lower().replace('0x', '') or f'{from_addr:08x}' in evidence, \
        'evidence does not name the transfer site'
    image = T.Image(str(binary))
    image.declare_data_regions(cfg['translate'].get('data_regions', []) + json.loads((source / 'inline-data.json').read_text()))
    image.noreturn_sites = frozenset(json.loads((source / 'nonreturning-calls.json').read_text()))
    owners = set()
    import re
    for path in (source / 'functions').glob('*.asm'):
        owners.update(int(m.group(1), 16) for m in re.finditer(r'^([0-9a-fA-F]{8})\s', path.read_text(), re.M))
    if target in owners or image.is_declared_data(target):
        raise ValueError(f'Target {target:08x} overlaps an existing entry or data claim')
    # witness: transfer site must decode as a non-immediate jump/call/ret in original bytes
    decoder = C.Cs(C.CS_ARCH_X86, C.CS_MODE_32)
    decoder.detail = True
    wit = next(decoder.disasm(image.data[from_addr - image.base:from_addr - image.base + 15], from_addr, count=1), None)
    if wit is None or wit.mnemonic not in ('jmp', 'call', 'ret'):
        raise ValueError('Transfer site does not decode as indirect transfer')
    if wit.operands and wit.operands[0].type == C.CS_OP_IMM:
        raise ValueError('Transfer site is a direct transfer, not computed')
    bounds = next((lo, hi) for lo, hi, _ in image.exec_ranges if lo <= target < hi)
    instructions = image.recover(target, owners, limit=4096, bounds=bounds)
    if not instructions or len(instructions) >= 4096 or instructions[0].addr != target:
        raise ValueError(f'No clean bounded original body at {target:08x}')
    if set(i.addr for i in instructions) & owners:
        raise ValueError('Candidate consumed an existing exported instruction')
    for ins in instructions:
        ci = next(decoder.disasm(image.data[ins.addr - image.base:ins.addr - image.base + 15], ins.addr, count=1))
        canonical = image.to_insn(ci)
        if (ins.addr, ins.mnem, ins.rep, ins.ops) != (canonical.addr, canonical.mnem, canonical.rep, canonical.ops):
            raise ValueError('Recovered instruction differs from original-byte decode')
    last = max(instructions, key=lambda i: i.addr)
    ci = next(decoder.disasm(image.data[last.addr - image.base:last.addr - image.base + 15], last.addr, count=1))
    end = last.addr + ci.size
    name = f'original_dispatcher_helper_{target:08x}'
    text = '\n'.join(f"{i.addr:08x}  {i.mnem + ('.' + i.rep if i.rep else '')} {','.join(i.ops)}".rstrip() for i in instructions) + '\n'
    parsed = T.parse_listing_text(text)
    assert [(i.addr, i.mnem, i.rep, i.ops) for i in parsed] == [(i.addr, i.mnem, i.rep, i.ops) for i in instructions]
    rows = (source / 'functions.tsv').read_text(encoding='utf-8').splitlines()
    indexed = {int(line.split('\t')[0], 16): line.split('\t') for line in rows[1:]}
    fn = T.Function(target, name, end - target, parsed)
    tr = T.Translator(image, set(indexed) | {target}, Opts())
    fn.measure(image)
    tr.prepare(fn)
    emitted = '\n'.join(tr.translate(fn))
    # additive curation
    shutil.copytree(source, out)
    (out / 'functions' / f'{target:08x}.asm').write_text(text, encoding='utf-8', newline='\n')
    indexed[target] = [f'{target:08x}', name, str(end - target), 'assembly',
                       'boot-probe-observed original computed dispatcher entry']
    (out / 'functions.tsv').write_text(rows[0] + '\n' + '\n'.join('\t'.join(indexed[a]) for a in sorted(indexed)) + '\n', encoding='utf-8')
    curated = T.read_curated(str(source / 'globals.toml'))
    prior = json.loads(json.dumps(curated))
    curated.setdefault('entries', {})[name] = target
    globals_text = '# Additive boot-probe-observed dispatcher entry; no return contract inferred.\n'
    for section, values in curated.items():
        globals_text += f'\n[{section}]\n'
        for k, v in sorted(values.items()):
            globals_text += f'{k} = ' + (f'0x{v:08x}' if isinstance(v, int) else json.dumps(v)) + '\n'
    (out / 'globals.toml').write_text(globals_text, encoding='utf-8')
    prev_manifest = json.loads((source / 'dispatcher-helper-curation.json').read_text(encoding='utf-8'))
    helper = dict(target=target, name=name, end=end, instruction_count=len(instructions),
                  bounds=list(bounds), listing_sha256=hashlib.sha256(text.encode()).hexdigest(),
                  generated_c_sha256=hashlib.sha256(emitted.encode()).hexdigest(),
                  observed_transfer_evidence=[dict(probe='translated boot probe (game_boot_probe)',
                                                   transfer_site=f'{from_addr:08x}',
                                                   witness_bytes=bytes(wit.bytes).hex(),
                                                   witness=f'{wit.mnemonic} {wit.op_str}')])
    prev_manifest['helpers'].append(helper)
    prev_manifest['boot_observed_targets'] = prev_manifest.get('boot_observed_targets', []) + [f'{target:08x}']
    (out / 'dispatcher-helper-curation.json').write_text(json.dumps(prev_manifest, indent=2), encoding='utf-8')
    print(json.dumps(dict(state='prepared', target=f'{target:08x}', instructions=len(instructions),
                          output=str(out)), indent=2))


if __name__ == '__main__':
    main()
