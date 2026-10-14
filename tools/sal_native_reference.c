/* Execute group-2 /6 and /4 on real Windows x86, preserving caller state. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <intrin.h>

static BYTE *code;
static unsigned pos;
static DWORD result_value, result_flags;
static void byte(BYTE value) { code[pos++]=value; }
static void word(DWORD value) { memcpy(code+pos,&value,4); pos+=4; }

static void execute(DWORD seed, DWORD flags, unsigned count, unsigned immediate, unsigned group) {
    pos=0;
    byte(0x60); byte(0x9c); /* PUSHAD/PUSHFD caller state */
    byte(0xbd); word(seed); /* MOV EBP,seed */
    byte(0xb9); word(count); /* MOV ECX,count */
    byte(0x68); word(flags); byte(0x9d); /* load valid user flags */
    byte(immediate?0xc1:0xd3);
    byte(group==6?0xf5:0xe5); /* exact EBP group-2 /6 or /4 */
    if(immediate) byte((BYTE)count);
    byte(0x89); byte(0x2d); word((DWORD)(uintptr_t)&result_value);
    byte(0x9c); byte(0x8f); byte(0x05); word((DWORD)(uintptr_t)&result_flags);
    byte(0x9d); byte(0x61); byte(0xc3); /* restore flags/GPRs, RET */
    FlushInstructionCache(GetCurrentProcess(),code,pos);
    ((void(__cdecl*)(void))code)();
}

int main(void) {
    const DWORD seeds[]={0,1,0x80000000,0x7fffffff,0xffffffff,0x11223344,0x87654321,0xaaaaaaaa};
    const DWORD flags[]={0x202,0x243,0xad7};
    const unsigned counts[]={0,1,6,31,32,33,255};
    unsigned s,f,c,immediate,row=0;
    DWORD sal_value,sal_flags;
    int cpu[4];
    if(sizeof(void*)!=4) return 2;
    code=(BYTE*)VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
    if(!code) return 3;
    __cpuid(cpu,0);
    printf("{\"cpuid_leaf0\":[%u,%u,%u,%u],\"results\":[",(unsigned)cpu[0],(unsigned)cpu[1],(unsigned)cpu[2],(unsigned)cpu[3]);
    for(immediate=0;immediate<2;++immediate)
        for(s=0;s<sizeof(seeds)/sizeof(seeds[0]);++s)
            for(f=0;f<sizeof(flags)/sizeof(flags[0]);++f)
                for(c=0;c<sizeof(counts)/sizeof(counts[0]);++c) {
                    execute(seeds[s],flags[f],counts[c],immediate,6);
                    sal_value=result_value; sal_flags=result_flags;
                    execute(seeds[s],flags[f],counts[c],immediate,4);
                    printf("%s{\"immediate\":%u,\"seed\":%lu,\"initial_flags\":%lu,\"count\":%u,\"sal_value\":%lu,\"sal_flags\":%lu,\"shl_value\":%lu,\"shl_flags\":%lu}",
                        row++?",":"",immediate,(unsigned long)seeds[s],(unsigned long)flags[f],counts[c],
                        (unsigned long)sal_value,(unsigned long)sal_flags,(unsigned long)result_value,(unsigned long)result_flags);
                }
    puts("]}");
    VirtualFree(code,0,MEM_RELEASE);
    return 0;
}
