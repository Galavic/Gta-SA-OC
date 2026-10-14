/* Private x86 Windows reference: a generated UD2 routine and real exception context. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static DWORD mode, fault_ip, fault_sp, before_flags, before_regs[8];
static DWORD after_flags, after_regs[8], fault_record_code, exception_flags, exception_args;
static DWORD exception_offset, context_offset, after_sp_delta, faults;

static LONG CALLBACK handle_fault(EXCEPTION_POINTERS *info) {
    CONTEXT *ctx = info->ContextRecord;
    EXCEPTION_RECORD *rec = info->ExceptionRecord;
    if (rec->ExceptionCode != EXCEPTION_ILLEGAL_INSTRUCTION || ctx->Eip != fault_ip)
        return EXCEPTION_CONTINUE_SEARCH;
    ++faults;
    fault_record_code = rec->ExceptionCode;
    exception_flags = rec->ExceptionFlags;
    exception_args = rec->NumberParameters;
    exception_offset = (DWORD)(uintptr_t)rec->ExceptionAddress - fault_ip;
    context_offset = ctx->Eip - fault_ip;
    before_flags = ctx->EFlags;
    fault_sp = ctx->Esp;
    before_regs[0]=ctx->Eax; before_regs[1]=ctx->Ecx; before_regs[2]=ctx->Edx;
    before_regs[3]=ctx->Ebx; before_regs[4]=0; before_regs[5]=ctx->Ebp;
    before_regs[6]=ctx->Esi; before_regs[7]=ctx->Edi;
    if (mode) {
        ctx->Eax=0xabc001; ctx->Ecx=0xabc002; ctx->Edx=0xabc003; ctx->Ebx=0xabc004;
        ctx->Ebp=0xabc006; ctx->Esi=0xabc007; ctx->Edi=0xabc008;
        ctx->EFlags=0x243;
        ctx->Esp+=16;
    }
    ctx->Eip+=2;
    return EXCEPTION_CONTINUE_EXECUTION;
}

static void __cdecl snapshot(const DWORD *frame) {
    after_regs[0]=frame[7]; after_regs[1]=frame[6]; after_regs[2]=frame[5];
    after_regs[3]=frame[4]; after_regs[4]=0; after_regs[5]=frame[2];
    after_regs[6]=frame[1]; after_regs[7]=frame[0];
    after_sp_delta=frame[3]+4-fault_sp;
    after_flags=frame[8];
}

static BYTE *code;
static unsigned pos;
static void byte(BYTE value) { code[pos++]=value; }
static void word(DWORD value) { memcpy(code+pos,&value,4); pos+=4; }
static void dump_regs(const DWORD *regs) {
    unsigned i;
    putchar('[');
    for(i=0;i<8;++i) printf("%s%lu",i?",":"",(unsigned long)regs[i]);
    putchar(']');
}

int main(void) {
    static const DWORD seeds[8]={0x11223344,0x22334455,0x33445566,0x44556677,0,
                                0x55667788,0x66778899,0x778899aa};
    static const DWORD flags[3]={0x202,0x243,0xad7};
    unsigned fi, i, row=0;
    PVOID handler;
    if(sizeof(void*)!=4) return 2;
    code=(BYTE*)VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!code) return 3;
    handler=AddVectoredExceptionHandler(1,handle_fault);
    if(!handler) return 4;
    putchar('[');
    for(mode=0;mode<2;++mode) for(fi=0;fi<3;++fi) {
        faults=0; pos=0;
        byte(0x60); byte(0x9c); /* preserve caller PUSHAD/PUSHFD */
        byte(0x81); byte(0xec); word(128); /* private scratch stack */
        for(i=0;i<8;++i) if(i!=4) { byte((BYTE)(0xb8+i)); word(seeds[i]); }
        byte(0x68); word(flags[fi]); byte(0x9d);
        fault_ip=(DWORD)(uintptr_t)(code+pos);
        byte(0x0f); byte(0x0b);
        byte(0x9c); byte(0x60); byte(0xfc); /* snapshot flags/GPRs, then CLD for C */
        byte(0x8b); byte(0xc4); byte(0x50);
        byte(0xb8); word((DWORD)(uintptr_t)snapshot); byte(0xff); byte(0xd0);
        byte(0x83); byte(0xc4); byte(4+36);
        byte(0x8b); byte(0x25); word((DWORD)(uintptr_t)&fault_sp);
        byte(0x81); byte(0xc4); word(128); byte(0x9d); byte(0x61); byte(0xc3);
        FlushInstructionCache(GetCurrentProcess(),code,pos);
        ((void(__cdecl*)(void))code)();
        printf("%s{\"mode\":%lu,\"initial_flags\":%lu,\"faults\":%lu,"
               "\"code\":%lu,\"exception_flags\":%lu,\"nargs\":%lu,"
               "\"exception_offset\":%lu,\"context_offset\":%lu,"
               "\"before_flags\":%lu,\"after_flags\":%lu,\"esp_delta\":%lu,\"before_regs\":",
               row++?",":"",(unsigned long)mode,(unsigned long)flags[fi],(unsigned long)faults,
               (unsigned long)fault_record_code,(unsigned long)exception_flags,(unsigned long)exception_args,
               (unsigned long)exception_offset,(unsigned long)context_offset,
               (unsigned long)before_flags,(unsigned long)after_flags,(unsigned long)after_sp_delta);
        dump_regs(before_regs); printf(",\"after_regs\":"); dump_regs(after_regs); putchar('}');
    }
    puts("]");
    RemoveVectoredExceptionHandler(handler);
    VirtualFree(code,0,MEM_RELEASE);
    return 0;
}
