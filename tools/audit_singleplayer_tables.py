"""Record the original bytes behind the four observed strict table blockers."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import pefile
import capstone

ROOT = Path(__file__).resolve().parents[1]
variant = ROOT / "variants/singleplayer"
raw = (variant / "prepared/gta_sa.exe").read_bytes()
pe = pefile.PE(data=raw)
base = pe.OPTIONAL_HEADER.ImageBase
memory = pe.get_memory_mapped_image()
decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
sites = [(0x014684be, 0x014684be, 0x00411c38),
         (0x0146a49b, 0x0146a520, 0x00414379),
         (0x014a9bcc, 0x014a9c09, 0x00409503),
         (0x014b174a, 0x014b17cf, 0x004116e8)]
report = []
for caller, site, table in sites:
    offset = site - base
    instruction = next(decoder.disasm(memory[offset:offset + 16], site, count=1))
    entries = struct.unpack_from("<8I", memory, table - base)
    rows = [{"target": f"{target:08x}",
             "in_executable_section": any(base + section.VirtualAddress <= target <
                  base + section.VirtualAddress + section.Misc_VirtualSize and
                  section.Characteristics & 0x20000000 for section in pe.sections)}
            for target in entries]
    report.append(dict(caller=f"{caller:08x}", site=f"{site:08x}",
                       instruction=instruction.mnemonic + " " + instruction.op_str,
                       instruction_bytes=instruction.bytes.hex(), table=f"{table:08x}",
                       table_bytes=memory[table-base:table-base+32].hex(), slots=rows))
output = dict(executable_sha256=hashlib.sha256(raw).hexdigest(),
              scope="Static image bytes; runtime writes and execution not verified",
              table_gate_bypassed=False, tables=report)
(variant / "table-blocker-audit.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
for row in report:
    print(row["site"], row["instruction"], "table", row["table"],
          "targets", ",".join(slot["target"] for slot in row["slots"][:4]))
