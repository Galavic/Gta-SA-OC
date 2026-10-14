#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

typedef BOOL (WINAPI *InitSpinFn)(LPCRITICAL_SECTION, DWORD);
typedef BOOL (WINAPI *FeatureFn)(DWORD);

static BOOL call_init(InitSpinFn fn, CRITICAL_SECTION *cs, DWORD spin, LONG *delta) {
    DWORD before, after, answer;
    __asm {
        mov before, esp
        push spin
        push cs
        call fn
        mov answer, eax
        mov after, esp
    }
    *delta = (LONG)(after - before);
    return (BOOL)answer;
}

static BOOL call_feature(FeatureFn fn, DWORD feature, LONG *delta) {
    DWORD before, after, answer;
    __asm {
        mov before, esp
        push feature
        call fn
        mov answer, eax
        mov after, esp
    }
    *delta = (LONG)(after - before);
    return (BOOL)answer;
}

int main(void) {
    HMODULE kernel = GetModuleHandleA("kernel32.dll");
    InitSpinFn init = (InitSpinFn)GetProcAddress(kernel, "InitializeCriticalSectionAndSpinCount");
    FeatureFn feature = (FeatureFn)GetProcAddress(kernel, "IsProcessorFeaturePresent");
    const DWORD spins[] = {0, 1, 4000, 100000};
    const DWORD features[] = {0, 1, 2, 3, 6, 8, 9, 10, 12, 13, 17, 0xffffffff};
    const DWORD marker = 0x1234abcd;
    SYSTEM_INFO system;
    unsigned i;
    int failures = 0;
    GetSystemInfo(&system);
    if (!init || !feature) return 2;
    printf("{\"architecture\":\"Windows x86\",\"resolved\":true,\"system_processors\":%lu,\"initialization\":[", system.dwNumberOfProcessors);
    for (i = 0; i < sizeof(spins) / sizeof(spins[0]); ++i) {
        CRITICAL_SECTION cs;
        LONG delta;
        DWORD error, recursion[5];
        ULONG_PTR stored_spin;
        BOOL answer;
        ZeroMemory(&cs, sizeof(cs));
        SetLastError(marker);
        answer = call_init(init, &cs, spins[i], &delta);
        error = GetLastError();
        if (!answer) return 3;
        stored_spin = cs.SpinCount;
        recursion[0] = (DWORD)cs.RecursionCount;
        EnterCriticalSection(&cs);
        recursion[1] = (DWORD)cs.RecursionCount;
        EnterCriticalSection(&cs);
        recursion[2] = (DWORD)cs.RecursionCount;
        LeaveCriticalSection(&cs);
        recursion[3] = (DWORD)cs.RecursionCount;
        LeaveCriticalSection(&cs);
        recursion[4] = (DWORD)cs.RecursionCount;
        if (delta || error != marker || recursion[0] != 0 || recursion[1] != 1 || recursion[2] != 2 || recursion[3] != 1 || recursion[4] != 0) ++failures;
        printf("%s{\"requested_spin\":%lu,\"stored_spin\":%lu,\"return\":%d,\"stack_delta\":%ld,\"last_error\":%lu,\"last_error_preserved\":%s,\"recursion\":[%lu,%lu,%lu,%lu,%lu]}",
               i ? "," : "", spins[i], (DWORD)stored_spin, answer, delta, error, error == marker ? "true" : "false",
               recursion[0], recursion[1], recursion[2], recursion[3], recursion[4]);
        DeleteCriticalSection(&cs);
    }
    printf("],\"features\":[");
    for (i = 0; i < sizeof(features) / sizeof(features[0]); ++i) {
        LONG delta;
        BOOL answer;
        DWORD error;
        SetLastError(marker);
        answer = call_feature(feature, features[i], &delta);
        error = GetLastError();
        if (delta || error != marker || (answer != FALSE && answer != TRUE)) ++failures;
        printf("%s{\"id\":%lu,\"return\":%d,\"stack_delta\":%ld,\"last_error\":%lu,\"last_error_preserved\":%s}",
               i ? "," : "", features[i], answer, delta, error, error == marker ? "true" : "false");
    }
    printf("],\"failures\":%d}\n", failures);
    return failures ? 4 : 0;
}
