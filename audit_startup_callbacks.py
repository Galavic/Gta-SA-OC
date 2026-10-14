"""Read original startup wrappers and bound their computed constructor transfers.

This is a synthetic Unicorn reference, not a complete startup or browser test.
It never rewrites code or replaces imports/calls/branches with successful stubs.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import tomllib
from types import SimpleNamespace

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS, UC_X86_REG_ECX

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text())
    exe = ROOT / cfg["game"]["developer_exe"]
    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    assert sha == cfg["game"]["sha256"]
    image = T.Image(str(exe))
    header = (ROOT / "build/recomp/gen/funcs.h").read_text()
    known = {int(x, 16) for x in re.findall(r"#define FIDX_([0-9a-f]{8})", header)}
    cases = []
    for slot, wrapper, target, obj, continuation in (
        (0x008A54E8, 0x0084BF20, 0x014CD7F0, 0x00A9D500, 0x014CD823),
        (0x008A58DC, 0x0084DEA0, 0x00572B80, 0x00B6E310, 0x00572C13),
    ):
        assert image.rd32(slot) == wrapper
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(image.base, (len(image.data) + 4095) & ~4095)
        machine.mem_write(image.base, image.data)
        machine.mem_map(0x0EFF0000, 0x10000)
        machine.reg_write(UC_X86_REG_ESP, 0x0EFFFEB4)
        machine.mem_write(0x0EFFFEB4, struct.pack("<I", 0x44444444))
        machine.reg_write(UC_X86_REG_EFLAGS, 0x202)
        trace = []

        def observe(uc, address, size, _):
            trace.append(address)
            if address == target:
                uc.emu_stop()

        machine.hook_add(UC_HOOK_CODE, observe)
        machine.emu_start(wrapper, 0, count=3000)
        assert machine.reg_read(UC_X86_REG_EIP) == target
        assert machine.reg_read(UC_X86_REG_ECX) == obj
        cases.append(dict(table_slot=f"{slot:08x}", wrapper=f"{wrapper:08x}",
                          constructor=f"{target:08x}", object=f"{obj:08x}",
                          executed_instructions=len(trace),
                          trace_tail=[f"{a:08x}" for a in trace[-12:]],
                          initial_esp="0efffeb4", initial_eflags="00000202",
                          sentinel_return="44444444", other_registers_zero=True,
                          stop_before_constructor_execution=True,
                          required_pushed_continuation=f"{continuation:08x}",
                          continuation_already_translated=continuation in known))
    recoveries = []
    for target in (0x014CD7F0, 0x00572B80, 0x00826794, 0x005630FB):
        instructions = image.recover(target, known - {target}, limit=4096)
        assert instructions
        fn = T.Function(target, "startup_audit", instructions[-1].addr - target + 1, instructions)
        fn.measure(image)
        translator = T.Translator(image, known | {target}, SimpleNamespace(eager_flags=False))
        translator.all_insn_addrs = known | fn.addrs
        translator.prepare(fn)
        emitted = translator.translate(fn)
        assert not translator.unmodelled
        recoveries.append(dict(target=f"{target:08x}", instructions=len(instructions),
                               last_instruction=f"{instructions[-1].addr:08x}",
                               individual_emission_succeeded=bool(emitted),
                               prefix_hex=image.data[target-image.base:target-image.base+32].hex(),
                               recognized_seh_sites=fn.seh_sites,
                               full_discovery_and_link_verified=False))
    live_prefix = None
    for line in (ROOT / "build/browser-runtime.jsonl").read_text(encoding="utf-8").splitlines():
        for message in json.loads(line):
            if "untranslated code 014cd7f0, live bytes:" in message:
                live_prefix = bytes.fromhex(message.split("live bytes:", 1)[1].split(";", 1)[0])
    expected = image.data[0x014CD7F0-image.base:0x014CD7F0-image.base+32]
    assert live_prefix == expected
    handlers = []
    for handler in (0x0083A15E, 0x0083CF2A):
        ins = image.recover(handler, set(), limit=15)
        assert [(i.mnem, i.ops) for i in ins][-1] == ("JMP", ["0x821ea0"])
        handlers.append(dict(address=f"{handler:08x}", already_translated=handler in known,
                             instructions=[dict(address=f"{i.addr:08x}", mnemonic=i.mnem, operands=i.ops) for i in ins]))
    report = dict(executable_sha256=sha, original_bytes_modified=False,
                  reference="Unicorn x86 original bytes, bounded synthetic wrapper states",
                  constructor_014cd7f0_live_prefix_matches_original=True,
                  wrapper_cases=cases, individual_recoveries=recoveries,
                  original_constructor_handlers=handlers,
                  recommended_constructor_seeds=["014cd7f0", "00572b80"],
                  other_missing_code_candidates=["00826794", "005630fb"],
                  other_candidates_provenance="Earlier browser trace after legacy missing-code return-zero fallbacks; weaker reachability evidence",
                  excluded_until_current_guest_bytes_validated=["00405580", "0150f7aa"],
                  limitation="Does not execute the constructors, full startup, SEH dispatch, rendering, or gameplay. 00572b80 current live prefix has not been captured in strict mode.",
                  browser_execution_verified=False, playable_verified=False)
    (ROOT / "build/startup-callback-reference.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Two original computed constructor transfers verified; four missing fragments emit without unmodelled instructions")


if __name__ == "__main__":
    main()
