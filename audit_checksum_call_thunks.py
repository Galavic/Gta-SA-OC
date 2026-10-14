"""Exact original stack-thunk form with a bounded XOR checksum loop.

This recognizer checks every instruction in the form. It never infers a
contract from a sampled execution or removes the checksum from native code.
"""
import capstone as C
from capstone.x86_const import X86_REG_ESP

GUARDS = tuple(bytes.fromhex(f"50 16 17 9c 8b 04 24 f6 c4 01 74 05 b9 be 07 00 00 {op} c0 74 01 e8 9d 58")
               for op in ("31", "33"))


def inspect(image, site, target):
    decoder = C.Cs(C.CS_ARCH_X86, C.CS_MODE_32)
    decoder.detail = True
    blob = image.data[target-image.base:target-image.base+1024]
    prefix = list(decoder.disasm(blob, target, count=6))
    if len(prefix) != 6:
        return None
    def stack(op):
        return (op.type == C.CS_OP_MEM and op.size == 4 and op.mem.base == X86_REG_ESP
                and not op.mem.index and not op.mem.disp)
    a, push, sub, push2, swap, load = prefix
    if [i.mnemonic for i in prefix] != ["add", "push", "sub", "push", "xchg", "mov"]:
        return None
    if not (stack(a.operands[0]) and a.operands[1].type == C.CS_OP_IMM
            and stack(push.operands[0]) and stack(sub.operands[0])
            and sub.operands[1].type == C.CS_OP_IMM and stack(push2.operands[0])
            and stack(swap.operands[0]) and swap.operands[1].type == C.CS_OP_REG):
        return None
    reg = swap.operands[1].reg
    if reg == X86_REG_ESP or swap.operands[1].size != 4:
        return None
    if not (load.operands[0].type == C.CS_OP_REG and load.operands[0].reg == reg
            and load.operands[1].type == C.CS_OP_MEM and load.operands[1].size == 4
            and load.operands[1].mem.base == reg and not load.operands[1].mem.index
            and not load.operands[1].mem.disp):
        return None
    dispatch = decoder.reg_name(reg)
    cursor = load.address + load.size
    guards = []
    for _ in range(2):
        offset = cursor-target
        guard = next((g for g in GUARDS if blob[offset:offset+len(g)] == g), None)
        if guard is None:
            return None
        guards.append([cursor, cursor+len(guard)])
        cursor += len(guard)
    def neutral(ins):
        if ins.mnemonic == "nop":
            return True
        ops = ins.operands
        if len(ops) != 2 or ops[0].type != C.CS_OP_REG or ops[0].size != 4:
            return False
        if ins.mnemonic in ("mov", "xchg"):
            return ops[1].type == C.CS_OP_REG and ops[1].reg == ops[0].reg
        if ins.mnemonic == "lea":
            return (ops[1].type == C.CS_OP_MEM and ops[1].mem.base == ops[0].reg
                    and not ops[1].mem.index and not ops[1].mem.disp)
        return False
    suffix = []
    decoded_suffix = []
    for ins in decoder.disasm(blob[cursor-target:], cursor):
        decoded_suffix.append(ins)
        if not neutral(ins):
            suffix.append(ins)
        if ins.mnemonic == "jmp":
            break
    if len(suffix) != 21:
        return None
    try:
        allocation = suffix[0].operands[1].imm
        initializer = suffix[1].operands[1].imm & 0xffffffff
        count_word = suffix[2].operands[1].imm & 0xffffffff
        count = count_word & 0xffff
        acc = decoder.reg_name(suffix[4].operands[0].reg)
        source = suffix[4].operands[1].imm & 0xffffffff
        temp = decoder.reg_name(suffix[5].operands[1].reg)
        encoded = suffix[19].operands[1].imm & 0xffffffff
        ret = suffix[20].operands[0].imm & 0xffffffff
    except (IndexError, AttributeError):
        return None
    if not (0x10 <= allocation <= 0x40 and allocation % 4 == 0) or not 1 <= count <= 1000:
        return None
    if acc == temp or "esp" in (acc, temp) or dispatch in (acc, temp):
        return None
    # Some originals branch to a neutral instruction just before the next
    # checksum read. Require an actual instruction boundary in that exact
    # neutral run; never accept the accumulator reset or operand bytes.
    loop_head = suffix[13].operands[0].imm & 0xffffffff
    reset_end = suffix[7].address + suffix[7].size
    loop_prefix = [i for i in decoded_suffix if reset_end <= i.address < suffix[8].address]
    if (loop_head not in {suffix[8].address, *(i.address for i in loop_prefix)}
            or not all(neutral(i) for i in loop_prefix)):
        return None
    def slot(offset, width="dword"):
        if offset == 0:
            return f"{width} ptr [esp]"
        return f"{width} ptr [esp + {str(offset) if offset < 10 else hex(offset)}]"
    expected = [
        ("sub", f"esp, {allocation:#x}"),
        ("mov", f"{slot(allocation-4)}, {initializer:#x}"),
        ("mov", f"{slot(allocation-8)}, {count_word:#x}"),
        ("mov", f"{slot(allocation-12)}, {acc}"), ("mov", f"{acc}, {source:#x}"),
        ("mov", f"{slot(allocation-16)}, {temp}"),
        ("mov", f"{slot(allocation-4)}, {acc}"), ("xor", f"{acc}, {acc}"),
        ("mov", f"{temp}, {slot(allocation-4)}"), ("mov", f"{temp}, dword ptr [{temp}]"),
        ("xor", f"{acc}, {temp}"), ("add", f"{slot(allocation-4)}, 4"),
        ("dec", slot(allocation-8, "word")), ("jne", f"{loop_head:#x}"),
        ("mov", f"{temp}, {slot(allocation-16)}"), ("add", f"{dispatch}, {acc}"),
        ("mov", f"{acc}, {slot(allocation-12)}"), ("add", f"esp, {allocation:#x}"),
        ("xchg", f"dword ptr [esp], {dispatch}"),
        ("mov", f"dword ptr [esp + 4], {encoded:#x}"), ("jmp", f"{ret:#x}"),
    ]
    if [(i.mnemonic, i.op_str) for i in suffix] != expected:
        return None
    write, jump = suffix[-2:]
    if (ret != write.address+4 or write.size != 8
            or image.data[ret-image.base:ret-image.base+3] != b"\xc2\x04\x00"):
        return None
    original_return = site+5
    continuation = (original_return+a.operands[1].imm) & 0xffffffff
    metadata = (continuation-sub.operands[1].imm) & 0xffffffff
    end = jump.address+jump.size
    if not (original_return <= metadata and metadata+4 <= target
            and 0 < continuation-original_return <= 0x1000 and 0 <= continuation-end <= 2
            and image.base <= source and source+count*4 <= image.end):
        return None
    checksum = 0
    for offset in range(count):
        checksum ^= image.rd32(source+offset*4)
    destination = (image.rd32(metadata)+checksum) & 0xffffffff
    if (destination == original_return or target <= destination < end
            or not image.is_exec(destination) or image.is_declared_data(destination)
            or not image.is_exec(continuation) or image.is_declared_data(continuation)):
        return None
    instructions = image.recover(target, set(), bounds=(target, end))
    if not instructions or not any(i.addr == ret and i.mnem == "RET" for i in instructions):
        return None
    return dict(call_site=site, callee=target, original_return=original_return,
                changed_continuation=continuation, metadata=metadata, destination=destination,
                end=end, ret4=ret, prefix_bytes=image.data[target-image.base:end-image.base].hex(),
                metadata_bytes=image.data[metadata-image.base:metadata-image.base+4].hex(),
                checksum_form=dict(source=source, words=count, xor=checksum, guards=guards,
                                   canonical_instructions=len(instructions)))
