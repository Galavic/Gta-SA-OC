"""Prepare additive, original-byte dispatcher helper exports in a fresh tree.

Default is a read-only readiness check. --prepare requires a successful native
Windows SAL reference and retains every existing exported entry and contract.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tomllib

import capstone as C

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor/recomp-kit/tools/recomp/tests'))
from test_translate_insns import Opts
import translate as T


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='analysis/curated-core-checksum-neutral')
    parser.add_argument('--output', default='analysis/curated-core-dispatcher')
    parser.add_argument('--sal-proof', default='build/sal-native-reference.json')
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--finish-partial', action='store_true', help='Finish only a script-created tree that lacks its final manifest')
    args = parser.parse_args()
    cfg = tomllib.loads((ROOT / 'game.toml').read_text(encoding='utf-8'))
    T.configure(T.game_config.load(ROOT))
    source = ROOT / args.input
    out = ROOT / args.output
    coverage_path = ROOT / 'analysis/dispatcher-coverage.json'
    native_path = ROOT / 'analysis/dispatcher-efb6d0-audit.json'
    coverage = json.loads(coverage_path.read_text())
    observed = json.loads(native_path.read_text())
    if coverage['input'] != str(source.relative_to(ROOT)):
        raise ValueError('Coverage evidence belongs to another input')
    binary = ROOT / cfg['game']['developer_exe']
    exe_sha = digest(binary)
    if exe_sha != cfg['game']['sha256'] or exe_sha != coverage['executable_sha256'] or exe_sha != observed['executable_sha256']:
        raise ValueError('Original executable SHA differs from evidence')
    if args.prepare and out.exists() and not args.finish_partial:
        raise ValueError('Use a fresh output directory')
    if args.finish_partial and (not args.prepare or not out.is_dir() or (out / 'dispatcher-helper-curation.json').exists() or out.resolve() == source.resolve()):
        raise ValueError('Only an unfinished separate dispatcher curation can be resumed')
    proof_path = ROOT / args.sal_proof
    proof = json.loads(proof_path.read_text()) if proof_path.exists() else None
    if args.prepare and not (proof and proof.get('results_equal_on_defined_flags') is True
        and proof.get('case_pairs') == len(proof.get('results', []))
        and proof.get('native_instruction_executions') == 2*proof['case_pairs']
        and 'D3 F5' in proof.get('reference', '') and 'C1 F5' in proof.get('reference', '')
        and {r['immediate'] for r in proof['results']} == {0, 1}
        and any(r['count'] == 6 for r in proof['results'])):
        raise ValueError('Matching native Windows group-2 /6 SAL verification required')
    if proof:
        for row in proof['results']:
            count = row['count'] & 31
            mask = 0xffffffff if count == 0 else (0x8d5 & ~0x10 & (~0x800 if count > 1 else 0xffffffff))
            if row['sal_value'] != row['shl_value'] or (row['sal_flags'] ^ row['shl_flags']) & mask:
                raise ValueError('Native SAL/SHL result rows do not match on defined flags')
    image = T.Image(str(binary))
    image.declare_data_regions(cfg['translate'].get('data_regions', []) + json.loads((source / 'inline-data.json').read_text()))
    image.noreturn_sites = frozenset(json.loads((source / 'nonreturning-calls.json').read_text()))
    owners = set()
    for path in (source / 'functions').glob('*.asm'):
        owners.update(int(m.group(1), 16) for m in re.finditer(r'^([0-9a-fA-F]{8})\s', path.read_text(), re.M))
    rows = (source / 'functions.tsv').read_text().splitlines()
    indexed = {int(line.split('\t')[0], 16): line.split('\t') for line in rows[1:]}
    original_rows = {address: row[:] for address, row in indexed.items()}
    targets = {item['target'] for item in coverage['observed_indirect_targets']}
    if targets != {0xefb852, 0xefbbe1, 0xefbd66, 0xefc768, 0xefe922, 0xf002db, 0xf00b87}:
        raise ValueError('Observed helper entry set changed; review new evidence')
    witnessed = {t['successor'] for p in observed['probes'] for t in p['computed_native_transfers']
        if 0xefb6d0 <= t['instruction']['address'] < 0xefd4ca}
    if not targets <= witnessed:
        raise ValueError('A new target lacks original native execution evidence')
    decoder = C.Cs(C.CS_ARCH_X86, C.CS_MODE_32)
    decoder.detail = True
    candidates = []
    for target in sorted(targets):
        if target in indexed or target in owners or image.is_declared_data(target):
            raise ValueError(f'Target {target:08x} overlaps an existing entry or data claim')
        item = next(e for e in coverage['observed_indirect_targets'] if e['target'] == target)
        for witness in item['observed_native_transfer_evidence']:
            ins = witness['instruction']
            raw = bytes.fromhex(ins['bytes'])
            offset = ins['address']-image.base
            if image.data[offset:offset+len(raw)] != raw:
                raise ValueError('Original computed transfer bytes differ')
        bounds = next((lo, hi) for lo, hi, _ in image.exec_ranges if lo <= target < hi)
        instructions = image.recover(target, owners | (targets-{target}), limit=4096, bounds=bounds)
        if not instructions or len(instructions) >= 4096 or instructions[0].addr != target:
            raise ValueError(f'No clean bounded original body at {target:08x}')
        if set(i.addr for i in instructions) & owners:
            raise ValueError('Candidate consumed an existing exported instruction')
        for ins in instructions:
            ci = next(decoder.disasm(image.data[ins.addr-image.base:ins.addr-image.base+15], ins.addr, count=1))
            canonical = image.to_insn(ci)
            if (ins.addr, ins.mnem, ins.rep, ins.ops) != (canonical.addr, canonical.mnem, canonical.rep, canonical.ops):
                raise ValueError('Recovered instruction differs from original-byte decode')
        last = max(instructions, key=lambda i: i.addr)
        ci = next(decoder.disasm(image.data[last.addr-image.base:last.addr-image.base+15], last.addr, count=1))
        end = last.addr+ci.size
        name = f'original_dispatcher_helper_{target:08x}'
        text = '\n'.join(f"{i.addr:08x}  {i.mnem + ('.'+i.rep if i.rep else '')} {','.join(i.ops)}".rstrip() for i in instructions)+'\n'
        parsed = T.parse_listing_text(text)
        assert [(i.addr, i.mnem, i.rep, i.ops) for i in parsed] == [(i.addr, i.mnem, i.rep, i.ops) for i in instructions]
        fn = T.Function(target, name, end-target, parsed)
        tr = T.Translator(image, set(indexed) | targets, Opts())
        fn.measure(image)
        tr.prepare(fn)
        emitted = '\n'.join(tr.translate(fn))
        candidates.append(dict(target=target, name=name, end=end, text=text,
            instruction_count=len(instructions), bounds=list(bounds),
            listing_sha256=hashlib.sha256(text.encode()).hexdigest(),
            generated_c_sha256=hashlib.sha256(emitted.encode()).hexdigest(),
            observed_transfer_evidence=item['observed_native_transfer_evidence']))
    report = dict(original_executable_sha256=exe_sha, source_input=str(source.relative_to(ROOT)),
        coverage_report_sha256=digest(coverage_path), native_observation_sha256=digest(native_path),
        sal_native_proof_sha256=digest(proof_path) if proof else None,
        helpers=[{k: v for k, v in c.items() if k != 'text'} for c in candidates],
        existing_exports_removed=0, original_bytes_modified=False, new_data_regions=0,
        new_no_return_contracts=0, game_config_modified=False,
        original_native_execution_evidence=True, individual_emission_verified=True,
        helpers_wasm_execution_verified=False, complete_game_execution_verified=False,
        global_reachability_proven=False,
        scope='Additive native computed-entry body recovery and C emission; observations use bounded synthetic caller states, not global reachability or return proofs.')
    if not args.prepare:
        print(json.dumps(dict(state='ready_for_fresh_additive_curation', helpers=len(candidates),
                             native_sal_proof_present=bool(proof), output=str(out))))
        return
    if args.finish_partial:
        expected_paths = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
        expected_paths.update(f"functions/{c['target']:08x}.asm" for c in candidates)
        actual_paths = {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
        if actual_paths != expected_paths:
            raise ValueError('Partial tree does not contain exactly the copied input and seven additions')
        for path in source.rglob('*'):
            if path.is_file() and path.relative_to(source).as_posix() not in ('functions.tsv', 'globals.toml'):
                if path.read_bytes() != (out / path.relative_to(source)).read_bytes():
                    raise ValueError('Partial tree changed an original source file')
    else:
        shutil.copytree(source, out)
    for c in candidates:
        (out / 'functions' / f"{c['target']:08x}.asm").write_text(c['text'], encoding='utf-8', newline='\n')
        indexed[c['target']] = [f"{c['target']:08x}", c['name'], str(c['end']-c['target']), 'assembly', 'observed original computed dispatcher entry']
    (out / 'functions.tsv').write_text(rows[0]+'\n'+'\n'.join('\t'.join(indexed[a]) for a in sorted(indexed))+'\n', encoding='utf-8')
    curated = T.read_curated(str(source / 'globals.toml'))
    prior = json.loads(json.dumps(curated))
    curated.setdefault('entries', {}).update({c['name']: c['target'] for c in candidates})
    globals_text = '# Additive observed original dispatcher entries; no runtime/return contract inferred.\n'
    for section, values in curated.items():
        globals_text += f'\n[{section}]\n'
        for name, value in sorted(values.items()):
            globals_text += f'{name} = ' + (f'0x{value:08x}' if isinstance(value, int) else json.dumps(value))+'\n'
    (out / 'globals.toml').write_text(globals_text, encoding='utf-8')
    for path in source.rglob('*'):
        if path.is_file() and path.relative_to(source).as_posix() not in ('functions.tsv', 'globals.toml'):
            if path.read_bytes() != (out / path.relative_to(source)).read_bytes():
                raise ValueError('An existing input file was modified during additive curation')
    reread = T.read_curated(str(out / 'globals.toml'))
    written_rows = {int(line.split('\t')[0], 16): line.split('\t') for line in (out / 'functions.tsv').read_text().splitlines()[1:]}
    assert all(written_rows[address] == row for address, row in original_rows.items())
    assert all(reread[s][k] == v for s, values in prior.items() for k, v in values.items())
    for c in candidates:
        assert digest(out / 'functions' / f"{c['target']:08x}.asm") == c['listing_sha256']
    (out / 'dispatcher-helper-curation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(state='prepared', helpers=len(candidates), output=str(out), active_configuration_changed=False)))


if __name__ == '__main__':
    main()
