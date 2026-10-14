/* Fixture services around the actual seh.cpp/cpu.cpp/interp.cpp implementations. */
#include "imports.h"
#include "memory.h"
#include "profile.h"
#include "seh.h"
#include "thunks.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <string>

uint8_t *g_mem;
uint32_t g_watch_base, g_watch_len, g_dirty_count;
RecompDirty g_dirty[RECOMP_DIRTY_SLOTS];
static uint32_t next_heap=0x01000000, live_allocations;
static const uint32_t IP=0x00401000, SP=0x03008000, TEB=0x00100000, HANDLER=0x00402000;
static uint32_t mode, initial_flags, faults, before_flags, before_regs[8];
static uint32_t fault_code, fault_flags, fault_nargs, exception_offset, context_offset;
static std::string negative;
static bool resume_test, nested_test;
static uint32_t landing_runs, mod_unwind_sp, atomic_unwind_sp;
static const uint32_t LANDING=IP+0x200;

int log_level() { return 0; }
void log_msg(int, const char *fmt, ...) {
    va_list args; va_start(args,fmt); vfprintf(stderr,fmt,args); va_end(args); fputc('\n',stderr);
}
bool log_once(const char *,const char *,...) { return false; }
uint32_t heap_alloc(uint32_t bytes,bool zero,uint32_t alignment) {
    next_heap=(next_heap+alignment-1)&~(alignment-1);
    uint32_t at=next_heap; next_heap+=bytes;
    if(zero) memset(g_mem+at,0,bytes);
    ++live_allocations; return at;
}
bool heap_free(uint32_t) { if(!live_allocations) abort(); --live_allocations; return true; }
void sched_atomic_unwind_to_esp(uint32_t esp) { atomic_unwind_sp=esp; }

extern "C" {
const int recomp_profile_enabled=0;
uint32_t recomp_profile_depth() { return 0; }
void recomp_profile_truncate(uint32_t) {}
void recomp_profile_push(uint32_t) { abort(); }
void recomp_profile_pop() { abort(); }
uint32_t recomp_callback_depth() { return 0; }
void recomp_callback_truncate(uint32_t depth) { if(depth) abort(); }
void recomp_callback_reset(X86 *) {}
void recomp_callback_return(X86 *) { abort(); }
void mods_hooks_unwind_to_esp(uint32_t esp) { mod_unwind_sp=esp; }
void recomp_watch_hit(uint32_t,uint32_t,uint64_t) { abort(); }
void recomp_call(X86 *,uint32_t);
void recomp_jump(X86 *,uint32_t) { abort(); }
int32_t recomp_index_of(uint32_t) { return -1; }
int recomp_is_call_return(uint32_t) { return 0; }
int recomp_thunk_target_kind(uint32_t) { return 0; }
void fn_00401000(X86 *);
void fault_pushfd(X86 *);
void recomp_call(X86 *c,uint32_t target) {
    if(!resume_test) abort();
    if(target==IP) {
        if(nested_test) {
            wr32(SP+512,0xffffffff); wr32(SP+516,HANDLER); wr32(TEB,SP+512);
            jmp_buf *outer=recomp_seh_frame_enter(c);
            if(setjmp(*outer)) abort(); // this host call must never be reentered after return
            wr32(SP+256,SP+512); wr32(TEB,SP+256);
        }
        jmp_buf *inner=recomp_seh_frame_enter(c);
        if(setjmp(*inner)) abort();
        fn_00401000(c);
        return; // fault continuation abandons this host environment
    }
    if(target==IP+2) {
        recomp_seh_unwind(c,nested_test?SP+512:SP+256,LANDING,0,0x1234);
        recomp_seh_intercept(c,LANDING);
        abort(); // the persistent run-loop checkpoint must receive control
    }
    if(target==LANDING) {
        ++landing_runs; c->eip=GUEST_RETURN_SENTINEL; c->r[R_ESP]=SP+1024; c->r[R_EAX]=0x4242;
        return;
    }
    abort();
}
}

uint32_t guest_call(X86 *c,uint32_t handler,const uint32_t *args,int nargs) {
    if(handler!=HANDLER || nargs!=4 || args[3]!=0) abort();
    const uint32_t rec=args[0], ctx=args[2];
    if(resume_test && (rd32(rec+4)&2)) return 1;
    ++faults;
    fault_code=rd32(rec); fault_flags=rd32(rec+4); fault_nargs=rd32(rec+16);
    exception_offset=rd32(rec+12)-IP; context_offset=rd32(ctx+0xb8)-IP;
    before_flags=rd32(ctx+0xc0);
    const unsigned offsets[8]={0xb0,0xac,0xa8,0xa4,0xc4,0xb4,0xa0,0x9c};
    for(unsigned i=0;i<8;++i) before_regs[i]=i==4?0:rd32(ctx+offsets[i]);
    if(mode) {
        for(unsigned i=0;i<8;++i) if(i!=4) wr32(ctx+offsets[i],0xabc001+i);
        wr32(ctx+0xc0,0x243); wr32(ctx+0xc4,SP+16);
    }
    wr32(ctx+0xb8,IP+2);
    if(negative=="context") wr32(ctx,0x1000b);
    if(negative=="segment") wr32(ctx+0xbc,0x8);
    if(negative=="noncontinuable") wr32(rec+4,1);
    if(negative=="debug") wr32(ctx+0xc0,0x302);
    // guest_call preserves ESP/EIP but a real guest callback may clobber GPRs.
    for(unsigned i=0;i<8;++i) if(i!=4) c->r[i]=0xdeaf0000+i;
    x86_set_eflags(c,0x202);
    return negative=="unhandled"?1:0;
}

static void setup(X86 *c) {
    memset(c,0,sizeof(*c));
    static const uint32_t regs[8]={0x11223344,0x22334455,0x33445566,0x44556677,SP,
                                 0x55667788,0x66778899,0x778899aa};
    memcpy(c->r,regs,sizeof(regs));
    c->fs_base=TEB; c->eip=IP;
    x86_set_eflags(c,initial_flags);
    wr32(TEB,SP+256); wr32(TEB+4,SP+4096); wr32(TEB+8,SP-4096);
    wr32(SP+256,0xffffffff); wr32(SP+260,HANDLER);
    wr32(SP,0x00403000); wr16(IP,0x0b0f);
    faults=0;
}

static void regs_json(const uint32_t *regs) {
    putchar('['); for(unsigned i=0;i<8;++i) printf("%s%u",i?",":"",i==4?0:regs[i]); putchar(']');
}

int main(int argc,char **argv) {
    g_mem=(uint8_t*)calloc(1,0x04000000);
    if(!g_mem) return 2;
    if(argc>1) {
        negative=argv[1]; mode=0; initial_flags=0x202;
        X86 c; setup(&c);
        if(negative=="resume" || negative=="nested_resume") {
            resume_test=true; nested_test=negative=="nested_resume";
            recomp_run(&c,IP);
            if(landing_runs!=1 || c.r[R_EAX]!=0x4242 || live_allocations ||
               c.eip!=GUEST_RETURN_SENTINEL || recomp_seh_pending_target()!=0 ||
               mod_unwind_sp!=(nested_test?SP+512:SP+256) || atomic_unwind_sp!=mod_unwind_sp)
                return 6;
            puts("resumable checkpoint unwind verified"); free(g_mem); return 0;
        }
        if(negative=="patched" || negative=="patched_fault") {
            wr8(IP,0x90); wr8(IP+1,0x90); wr8(IP+2,0xc3);
            if(negative=="patched_fault") {
                const uint8_t bad[]={0x8b,0x05,0,0,0,0,0xc3};
                memcpy(g_mem+IP,bad,sizeof(bad));
            }
            fn_00401000(&c);
            if(negative=="patched_fault" || faults || c.eip!=0x00403000 || c.r[R_ESP]!=SP+4) return 3;
            puts("patched current bytes executed"); free(g_mem); return 0;
        }
        if(negative=="orphan") recomp_seh_frame_enter(&c);
        if(negative=="legacy") {
            recomp_seh_raise(&c,0xc000001d,0,0,0);
            return 4;
        }
        fn_00401000(&c);
        if(negative=="orphan") {
            recomp_seh_resume_boundary(&c);
            recomp_seh_unwind(&c,SP+256,IP,0,0);
            recomp_seh_intercept(&c,IP+2);
        }
        return 4; // every requested unsupported case must stop
    }
    unsigned row=0;
    const uint32_t flags[]={0x202,0x243,0xad7};
    putchar('[');
    for(mode=0;mode<2;++mode) for(unsigned fi=0;fi<3;++fi) {
        initial_flags=flags[fi]; X86 c; setup(&c);
        fn_00401000(&c);
        if(c.eip!=IP+2 || live_allocations) return 5;
        fault_pushfd(&c);
        uint32_t visible_flags=rd32(c.r[R_ESP]); c.r[R_ESP]+=4;
        printf("%s{\"mode\":%u,\"initial_flags\":%u,\"faults\":%u,\"code\":%u,"
               "\"exception_flags\":%u,\"nargs\":%u,\"exception_offset\":%u,\"context_offset\":%u,"
               "\"before_flags\":%u,\"after_flags\":%u,\"esp_delta\":%u,\"before_regs\":",
               row++?",":"",mode,initial_flags,faults,fault_code,fault_flags,fault_nargs,
               exception_offset,context_offset,before_flags,visible_flags,c.r[R_ESP]-SP);
        regs_json(before_regs); printf(",\"after_regs\":"); regs_json(c.r); putchar('}');
    }
    puts("]"); free(g_mem); g_mem=nullptr; return 0;
}
