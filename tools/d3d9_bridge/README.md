# Original guest Direct3D9 vertex bridge

`guest_vertex.h` is an isolated C++ component for the original 32-bit Windows
renderer. It does not replace the game engine or register a working graphics
device yet. Run `.venv/Scripts/python.exe tools/d3d9_bridge/verify.py` from the
project root to compile and execute fixtures on actual Windows x86 and Wasm.

The verifier checks native Windows SDK COM method slots and structure sizes;
then checks vertex offsets, blend representations, every UV dimension in each
of eight texture slots, primitive counts, overflowing/invalid guest addresses,
stdcall stack decoding, padded vertex staging and byte color order. The
independent Windows SDK/packed-structure checks establish the guest layout;
the same behavioral fixture executes in Wasm. They do not prove graphics or
full original game execution.

The pinned original EXE actually loads FVF `0x252` at `0x00814ddc` and calls
`IDirect3DDevice9::SetFVF` through guest vtable offset `0x164` at `0x00814e01`.
The verifier checks these bytes and the whole original EXE SHA256. That FVF is
XYZ + normal + diffuse + two 2D UV sets, totaling 44 bytes. The component accepts
this layout; actual rendering with candidate shaders is still unverified.

## Integration boundary

1. Register `d3d9.dll!Direct3DCreate9` as a real shim. Return an allocated guest
   COM object containing a **guest 32-bit pointer** to its vtable. Allocate each
   method using the runtime's import trampoline services and Windows SDK order.
2. Keep host backend pointers in a separate handle registry. The candidate's
   C++ objects/vtables are not guest pointers. Its `IDirect3DDevice9` starts with
   Clear after IUnknown; native Clear is slot43. Never copy its vtable into guest
   memory. SDK-checked native slots: CreateDevice16 on IDirect3D9; Clear43,
   DrawPrimitiveUP83, SetFVF89 on IDirect3DDevice9.
3. A SetFVF shim reads guest `this` and DWORD FVF, decodes it and rejects layouts
   the chosen implementation cannot execute. Decode before changing current
   device state. Do not rely on candidate enum definitions: XYZB2 is wrongly
   defined as `0x1000`, and SPECULAR as `0x40`, in the pinned candidate header.
4. For DrawPrimitiveUP, call `decode_draw_up(memory, size, c->r[R_ESP], fvf, draw)`.
   Its stack is return address, this, primitive type, count, vertices and stride.
   On the normal runtime import path, set EAX to HRESULT and let
   `imports_dispatch` pop the return plus five stdcall arguments. **Do not also
   set ESP to `draw.next_esp`**: that value is only for a standalone dispatcher.
   Object identity/lifetime, guest vtable validity and render state still need
   registry checks outside this byte parser.
5. Use `snapshot_draw_up` to copy actual attributes to a tightly packed staging
   buffer, and pass its decoded stride to the host backend. Candidate UP uploads
   and copies `vertex_count * stride`, including final padding; a direct guest
   pointer may overread bytes beyond the final vertex attributes. Staging avoids
   that and avoids retaining guest memory across a draw.
6. Preserve packed guest BGRA diffuse colors for candidate UP: that method
   already swaps red/blue. `color_to_rgba` is for a backend that needs a converted
   color, not an additional conversion before candidate UP. The candidate
   DrawPrimitive/buffer path uses raw normalized byte attributes without the UP
   swap; that separate path needs its own color handling.

`candidate_layout_supported` is a layout filter only, not a claim that every
render state or shader is implemented. It rejects weights, blend indices,
point size, specular, homogeneous XYZW, >2 UV sets and non-2D UVs. The parser can
still describe those layouts for a future backend.

## Remaining graphics limitations

The pinned MIT candidate `vendor/d3d9-webgl` revision
`9f2543a8488133182cef920a58763765cff3ddf7` lacks programmable shaders and vertex
declarations, has partial render-state handling and lighting, and does not
provide native COM ABI order. Methods that return success with null shader or
declaration outputs must become genuine implementations or explicit failures
before exposing them to the original game. No active runtime/config file was
changed by this component.

Windows layout references:
[FVF](https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dfvf),
[UV dimensions](https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dfvf-texcoordsizen),
[vertex field sizes](https://github.com/MicrosoftDocs/win32/blob/docs/desktop-src/direct3d9/accessing-the-contents-of-a-vertex-buffer.md).
