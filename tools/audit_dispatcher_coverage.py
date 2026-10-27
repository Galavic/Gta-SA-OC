"""Compare observed native dispatcher entries with all active curated exports.

Candidate recovery/emission is research only: it does not alter active inputs,
admit new bodies, or establish a whole-game dispatch/return contract.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

import capstone as C

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/recomp-kit/tools/recomp/tests'))
from test_translate_insns import Opts
import translate as T


def main():
    cfg = tomllib.loads((ROOT / 'game.toml').read_text(encoding='utf-8'))
    T.configure(T.game_config.load(ROOT))
    source = ROOT / cfg['translate']['listings']
    observations = json.loads((ROOT / 'analysis/dispatcher-efb6d0-audit.json').read_text())
    binary = ROOT / cfg['game']['developer_exe']
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == observations['executable_sha256']
    image = T.Image(str(binary))
    image.declare_data_regions(cfg['translate'].get('data_regions', []) +
        json.loads((ROOT / cfg['translate']['data_regions_file']).read_text()))
    image.noreturn_sites = frozenset(json.loads((ROOT / cfg['translate']['no_fallthrough_calls_file']).read_text()))
    starts = {int(row.split('\t')[0], 16) for row in
        (source / 'functions.tsv').read_text().splitlines()[1:]}
    owners = {}
    for listing in sorted((source / 'functions').glob('*.asm')):
        for line in listing.read_text(encoding='utf-8').splitlines():
            m = re.match(r'^([0-9a-fA-F]{8})\s', line)
            if m:
                owners.setdefault(int(m[1], 16), []).append(listing.stem)
    missing_from_dispatcher = set()
    evidence = {}
    for probe in observations['probes']:
        missing_from_dispatcher.update(probe['executed_dispatcher_region_boundaries_absent_from_export'])
        assert not probe['dynamically_modified_executed_bytes'], 'Source-byte audit cannot assert modified-code equivalence'
        for transfer in probe['computed_native_transfers']:
            ins = transfer['instruction']
            if not 0xefb6d0 <= ins['address'] < 0xefd4ca:
                continue
            address = ins['address']
            raw = bytes.fromhex(ins['bytes'])
            assert image.data[address-image.base:address-image.base+len(raw)] == raw
            evidence.setdefault(transfer['successor'], []).append(dict(probe_start=probe['start'], **transfer))
    decoder = C.Cs(C.CS_ARCH_X86, C.CS_MODE_32)
    coverage = []
    all_entries = starts | set(evidence)
    for target, witnesses in sorted(evidence.items()):
        first = next(decoder.disasm(image.data[target-image.base:target-image.base+15], target, count=1), None)
        item = dict(target=target, original_first_instruction=dict(address=first.address,
            bytes=bytes(first.bytes).hex(), mnemonic=first.mnemonic, operands=first.op_str) if first else None,
            active_export_owners=owners.get(target, []), exported_function_start=target in starts,
            observed_native_transfer_evidence=witnesses)
        if target not in owners:
            bounds = next((lo, hi) for lo, hi, _ in image.exec_ranges if lo <= target < hi)
            candidate = image.recover(target, set(owners), limit=4096, bounds=bounds)
            item['candidate_recovery'] = dict(instruction_count=len(candidate), bounds=list(bounds),
                instruction_limit=4096, stops_at_any_active_export_instruction=True,
                minimum_address=min((i.addr for i in candidate), default=None),
                maximum_instruction_address=max((i.addr for i in candidate), default=None),
                admission_to_active_analysis=False)
            if candidate:
                last = max(candidate, key=lambda i: i.addr)
                ci = next(decoder.disasm(image.data[last.addr-image.base:last.addr-image.base+15], last.addr, count=1))
                fn = T.Function(target, f'dispatcher_probe_{target:08x}', last.addr+ci.size-target, candidate)
                tr = T.Translator(image, all_entries, Opts())
                try:
                    fn.measure(image)
                    tr.prepare(fn)
                    emitted = '\n'.join(tr.translate(fn))
                    item['emission_probe'] = dict(state='emitted', generated_c_sha256=hashlib.sha256(emitted.encode()).hexdigest(),
                        generated_c_bytes=len(emitted.encode()), linked_or_executed=False)
                except T.TranslateError as exc:
                    item['emission_probe'] = dict(state='failed', error=str(exc), linked_or_executed=False)
                    match = re.match(r'([0-9a-fA-F]{8})\s', str(exc))
                    if match:
                        addr = int(match[1], 16)
                        fault = next(decoder.disasm(image.data[addr-image.base:addr-image.base+15], addr, count=1), None)
                        if fault:
                            item['emission_probe']['original_failed_instruction'] = dict(address=addr,
                                bytes=bytes(fault.bytes).hex(), mnemonic=fault.mnemonic, operands=fault.op_str)
            else:
                item['emission_probe'] = dict(state='no_clean_bounded_recovery', linked_or_executed=False)
        coverage.append(item)
    uncovered = sorted(missing_from_dispatcher-set(owners))
    report = dict(executable_sha256=observations['executable_sha256'], input=str(source.relative_to(ROOT)),
        active_input_modified=False, original_bytes_modified=False,
        observed_missing_from_dispatcher_export=len(missing_from_dispatcher),
        covered_by_other_active_exports=len(missing_from_dispatcher & set(owners)),
        uncovered_by_any_active_export=uncovered, observed_indirect_targets=coverage,
        scope='Original-byte-verified observed targets; bounded individual C emission only. No global discovery, link or runtime verification.',
        admission_requirements=('Verify complete native body ownership and incoming/outgoing edges, register target as independent '
            'computed entry, preserve original bytes, run native-vs-Wasm dispatcher differential checks with valid caller state, '
            'then pass full strict discovery/link. Successful individual emission alone does not admit a contract or new body.'))
    output = ROOT / 'analysis/dispatcher-coverage.json'
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(uncovered_boundaries=len(uncovered), indirect_targets=len(coverage),
        targets=[dict(target=hex(i['target']), owners=i['active_export_owners'],
                      emission=i.get('emission_probe')) for i in coverage])))


if __name__ == '__main__':
    main()
