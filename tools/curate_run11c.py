"""Quarantine the 19-function 011c8-011dc junk run + closure (q8 -> q9)."""
import hashlib
import json
import re
import shutil
import tomllib
from collections import defaultdict, deque
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
ENTRY = 0x00825330
SEEDS = [0x011cab50, 0x011ccfc0, 0x011ccfe0, 0x011cd000, 0x011cd01a, 0x011cd130,
         0x011cd149, 0x011cd260, 0x011cd280, 0x011cd2a0, 0x011cd2c0, 0x011cd2e0,
         0x011cd370, 0x011cd390, 0x011cd3bc, 0x011cd600, 0x011cd610, 0x011cda90,
         0x011cdaa0]

cfg = tomllib.loads((ROOT / 'game.toml').read_text(encoding='utf-8'))
binary = ROOT / cfg['game']['developer_exe']
raw = binary.read_bytes()
assert hashlib.sha256(raw).hexdigest() == cfg['game']['sha256']
pe = pefile.PE(data=raw)
base = pe.OPTIONAL_HEADER.ImageBase

def secname(va):
    for s in pe.sections:
        if base + s.VirtualAddress <= va < base + s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            return s.Name.rstrip(b'\0').decode('ascii', 'replace')
    return None

src = ROOT / cfg['translate']['listings']
fdir = src / 'functions'
for a in SEEDS:
    assert (fdir / f'{a:08x}.asm').is_file(), f'{a:08x} has no listing'

call_re = re.compile(r'^([0-9a-fA-F]+)\s+([A-Z]+)\s*(.*)$')
jmps = {"JMP", "JZ", "JE", "JNZ", "JNE", "JB", "JAE", "JA", "JBE", "JG", "JGE",
        "JL", "JLE", "JO", "JNO", "JS", "JNS", "JP", "JNP", "JCXZ", "JECXZ",
        "LOOP", "LOOPE", "LOOPNE"}
edges = defaultdict(set)
fns = set()
texts = {}
for p in fdir.glob('*.asm'):
    try:
        fn = int(p.stem, 16)
    except ValueError:
        continue
    fns.add(fn)
    text = p.read_text(encoding='utf-8', errors='replace')
    texts[fn] = text
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = call_re.match(line)
        if not m:
            continue
        if m.group(2) in ({'CALL'} | jmps):
            m2 = re.search(r'0x([0-9a-fA-F]+)', m.group(3))
            if m2:
                edges[fn].add(int(m2.group(1), 16))
seen = {ENTRY}
queue = deque([ENTRY])
while queue:
    for target in edges.get(queue.popleft(), ()):
        if target in fns and target not in seen:
            seen.add(target)
            queue.append(target)

q = set(SEEDS)
frontier = list(SEEDS)
while frontier:
    cur = frontier.pop(0)
    for c, ts in edges.items():
        if cur in ts and c not in q:
            if c in seen:
                raise ValueError(f'Closure reaches reachable code at {c:08x}; aborting')
            q.add(c)
            frontier.append(c)
print('closure size:', len(q))
assert not (q & seen), 'hits reachable'
refs = defaultdict(set)
for caller, targets in edges.items():
    for target in targets & q:
        refs[target].add(caller)
live = sorted({c for s in refs.values() for c in s} & seen)
assert not live, f'live refs: {live}'
hexpat = re.compile(r'0x([0-9a-f]{6,8})')
mentioning = sorted(fn for fn in seen
                    if any(int(m.group(1), 16) in q for m in hexpat.finditer(texts[fn].lower())))
assert not mentioning, f'reachable mentions: {mentioning}'
curated = tomllib.loads((src / 'globals.toml').read_text(encoding='utf-8'))
drop = sorted(name for sec, vals in curated.items() if isinstance(vals, dict)
              for name, val in vals.items() if isinstance(val, int) and val in q)
print('globals to drop:', drop)

out = ROOT / 'analysis/curated-core-neutral-q9'
assert not out.exists()
shutil.copytree(src, out)
records = []
for addr in sorted(q):
    listing = out / 'functions' / f'{addr:08x}.asm'
    digest = hashlib.sha256(listing.read_bytes()).hexdigest()
    listing.unlink()
    records.append(dict(address=f'{addr:08x}', reason='run_sweep_011c8_011dc_unreachable',
                        section=secname(addr), listing_sha256=digest,
                        direct_referrers=sorted(f'{c:08x}' for c in refs.get(addr, ())),
                        reachable_from_entry=False))
rows = (out / 'functions.tsv').read_text(encoding='utf-8').splitlines()
kept = [rows[0]] + [r for r in rows[1:] if r.strip() and int(r.split('\t')[0], 16) not in q]
assert len(rows) - 1 - (len(kept) - 1) == len(q)
(out / 'functions.tsv').write_text('\n'.join(kept) + '\n', encoding='utf-8')
text = '# Round q9: sweep of 011c8-011dc unreachable run.\n'
for section, vals in curated.items():
    text += f'\n[{section}]\n'
    for name, val in sorted(vals.items()):
        if name in drop:
            continue
        text += f'{name} = ' + (f'0x{val:08x}' if isinstance(val, int) else json.dumps(val)) + '\n'
(out / 'globals.toml').write_text(text, encoding='utf-8')
r = json.loads((out / 'quarantine.json').read_text())
r['round_q9_run_sweep'] = dict(seeds=[f'{a:08x}' for a in SEEDS], removed=len(records))
(out / 'quarantine.json').write_text(json.dumps(r, indent=2))
print(f'Quarantined {len(records)}. Output: {out}')
