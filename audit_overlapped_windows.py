"""Measure native Windows file I/O before implementing the guest shims.

Only a generated test file in build/ is opened. Original GTA assets are not
modified. This reference is not execution of the game or its audio engine.
"""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Overlapped(C.Structure):
    _fields_ = [("Internal", C.c_size_t), ("InternalHigh", C.c_size_t),
                ("Offset", W.DWORD), ("OffsetHigh", W.DWORD), ("hEvent", W.HANDLE)]


def main():
    api = C.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE]
    api.CreateFileW.restype = W.HANDLE
    api.CreateEventW.argtypes = [W.LPVOID, W.BOOL, W.BOOL, W.LPCWSTR]
    api.CreateEventW.restype = W.HANDLE
    api.CloseHandle.argtypes = [W.HANDLE]
    api.CloseHandle.restype = W.BOOL
    api.ReadFile.argtypes = [W.HANDLE, W.LPVOID, W.DWORD, C.POINTER(W.DWORD), C.POINTER(Overlapped)]
    api.ReadFile.restype = W.BOOL
    api.GetOverlappedResult.argtypes = [W.HANDLE, C.POINTER(Overlapped), C.POINTER(W.DWORD), W.BOOL]
    api.GetOverlappedResult.restype = W.BOOL
    api.SetFilePointerEx.argtypes = [W.HANDLE, C.c_longlong, C.POINTER(C.c_longlong), W.DWORD]
    api.SetFilePointerEx.restype = W.BOOL
    api.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    api.WaitForSingleObject.restype = W.DWORD
    path = ROOT / "build/overlapped-reference.bin"
    path.parent.mkdir(exist_ok=True)
    payload = b"0123456789abcdef\n"
    path.write_bytes(payload)
    rows = []
    for asynchronous in (False, True):
        handle = api.CreateFileW(str(path), 0x80000000, 3, None, 3, 0x80 | (0x40000000 if asynchronous else 0), None)
        if handle == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        event = api.CreateEventW(None, True, False, None)
        if not event:
            api.CloseHandle(handle)
            raise C.WinError(C.get_last_error())
        try:
            for offset in (0, 3, 16, 17, 18, 1 << 32):
                for requested in (0, 1, 4, 100):
                    if not api.SetFilePointerEx(handle, 3, None, 0):
                        raise C.WinError(C.get_last_error())
                    operation = Overlapped(0, 0, offset & 0xffffffff, offset >> 32, event)
                    buffer = C.create_string_buffer(max(requested, 1))
                    read = W.DWORD(0x55555555)
                    C.set_last_error(0)
                    success = bool(api.ReadFile(handle, buffer, requested, C.byref(read), C.byref(operation)))
                    immediate_error = C.get_last_error()
                    transferred = W.DWORD(0xaaaaaaaa)
                    C.set_last_error(0)
                    completed = bool(api.GetOverlappedResult(handle, C.byref(operation), C.byref(transferred), True))
                    completed_error = C.get_last_error()
                    position = C.c_longlong()
                    if not api.SetFilePointerEx(handle, 0, C.byref(position), 1):
                        raise C.WinError(C.get_last_error())
                    expected = payload[offset:offset + requested]
                    if completed and (transferred.value != len(expected) or buffer.raw[:transferred.value] != expected):
                        raise AssertionError("Native I/O bytes differ from the test file")
                    rows.append(dict(asynchronous_handle=asynchronous, offset=offset, requested=requested,
                                     readfile_success=success, readfile_error=immediate_error,
                                     readfile_count=read.value, completed=completed,
                                     completed_error=completed_error, transferred=transferred.value,
                                     internal_status=operation.Internal, internal_count=operation.InternalHigh,
                                     final_file_position=position.value,
                                     event_signalled=api.WaitForSingleObject(event, 0) == 0,
                                     bytes=buffer.raw[:transferred.value].hex() if completed else ""))
        finally:
            api.CloseHandle(event)
            api.CloseHandle(handle)
    report = dict(native_windows_reference=True, test_file=str(path), original_assets_modified=False,
                  game_execution_verified=False, cases=rows)
    (ROOT / "build/overlapped-windows-reference.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Verified {len(rows)} native Windows OVERLAPPED file-read cases")


if __name__ == "__main__":
    main()
