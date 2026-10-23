"""Bounded original-byte diagnostics; never admits translation contracts."""
from pathlib import Path
import hashlib
import json
import struct
import tomllib
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
import verify_branch_wasm as B

ROOT = Path(__file__).resolve().parents[1]
STACK = 0x03008000
SITES = ((0x00f921f4, 0x00f92202), (0x00fd63b5, 0x00fd63c1))


def main():
    cfg = tomllib.loads((ROOT / "game.toml").read_text(encoding="utf-8"))
    path = ROOT / cfg["game"]["developer_exe"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == cfg["game"]["sha256"]
    image = B.T.Image(str(path))
    results = []
    for site, target in SITES:
        assert image.rd8(site) == 0xe8
        assert (site + 5 + image.rd32(site + 1)) & 0xffffffff == target
        for seed in (0, 0x11223300, 0xaabbcc00):
            for flags in B.FLAGS:
                uc = Uc(UC_ARCH_X86, UC_MODE_32)
                uc.mem_map(image.base, (len(image.data) + 0xfff) & ~0xfff)
                uc.mem_write(image.base, image.data)
                uc.mem_map(STACK & ~0xffff, 0x10000)
                uc.mem_map(0x10000, 0x1000)
                descriptors = bytearray(64)
                for slot, value in {1:0x00cf9a000000ffff, 2:0x00cf92000000ffff,
                                    3:0x00cffa000000ffff, 4:0x00cff2000000ffff}.items():
                    descriptors[slot*8:slot*8+8] = struct.pack("<Q", value)
                uc.mem_write(0x10000, bytes(descriptors))
                uc.reg_write(B.UC_X86_REG_GDTR, (0, 0x10000, 63, 0))
                uc.reg_write(B.UC_X86_REG_CS, 8)
                uc.reg_write(B.UC_X86_REG_SS, 16)
                bootstrap = 0x02f00000
                uc.mem_map(bootstrap, 0x1000)
                uc.mem_write(bootstrap, b"\xcf")
                uc.mem_write(STACK+0x100, struct.pack("<IIIII", target, 0x1b, 0x202, STACK, 0x23))
                uc.reg_write(B.REGISTERS[4], STACK+0x100)
                uc.emu_start(bootstrap, target, count=10)
                registers = [seed+i for i in range(8)]
                registers[4] = STACK
                for reg, value in zip(B.REGISTERS, registers):
                    uc.reg_write(reg, value)
                uc.reg_write(B.UC_X86_REG_EFLAGS, flags)
                uc.mem_write(STACK, struct.pack("<I", site+5))
                row = dict(call_site=f"{site:08x}", callee=f"{target:08x}",
                           seed=seed, initial_flags=flags, steps=0)
                def observe(machine, address, size, user):
                    row["steps"] += 1
                    if machine.mem_read(address, 1)[0] in (0xc2, 0xc3):
                        row["ret_site"] = address
                        machine.emu_stop()
                def write(machine, access, address, size, value, user):
                    # Reloading SS sets the accessed bit in the private GDT.
                    private_stack = STACK-0x8000 <= address and address+size <= STACK+0x8000
                    private_gdt = 0x10000 <= address and address+size <= 0x10040
                    if not (private_stack or private_gdt):
                        row["outside_stack_write"] = address
                        machine.emu_stop()
                uc.hook_add(UC_HOOK_CODE, observe)
                uc.hook_add(UC_HOOK_MEM_WRITE, write)
                try:
                    uc.emu_start(target, 0, count=10000)
                    if "ret_site" in row and "outside_stack_write" not in row:
                        # The first run stopped before RET; its stack contains
                        # the exact destination and cleanup operand to inspect.
                        esp = uc.reg_read(B.REGISTERS[4])
                        row["ret_target"] = int.from_bytes(uc.mem_read(esp, 4), "little")
                        row["ret_esp"] = esp
                        row["next_stack_word"] = int.from_bytes(uc.mem_read(esp+4, 4), "little")
                        row["caller_stack_word"] = int.from_bytes(uc.mem_read(STACK, 4), "little")
                        row["ret_bytes"] = bytes(uc.mem_read(row["ret_site"], 3)).hex()
                    else:
                        row["stop"] = "outside_stack_write" if "outside_stack_write" in row else "instruction_budget"
                except UcError as error:
                    row["stop"] = str(error)
                row["last_eip"] = uc.reg_read(B.UC_X86_REG_EIP)
                results.append(row)
    out = ROOT / "analysis/complex-local-prefix-traces.json"
    out.write_text(json.dumps(dict(executable_sha256=cfg["game"]["sha256"],
                                  contracts_admitted=False, game_execution_verified=False,
                                  scope="Original native prefixes in private synthetic caller states; stops before RET", results=results), indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
