#ifdef _WIN32
#define CINTERFACE
#include <windows.h>
#include <d3d9.h>
#endif
#include "guest_vertex.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>

using namespace gtasa_d3d9;
static uint32_t checks = 0;
static void require(bool condition) {
    ++checks;
    if (!condition) { std::fprintf(stderr, "failed check %u\n", checks); std::abort(); }
}
struct WorldVertex { float xyz[3], normal[3]; uint32_t diffuse; float uv[2]; };
struct ScreenVertex { float xyzw[4]; uint32_t diffuse; float uv[2]; };
struct TwoTextureVertex { float xyz[3]; uint32_t diffuse, specular; float uv[2], uvw[3]; };
static void write32(uint8_t* memory, uint32_t address, uint32_t value) {
    for (unsigned i=0; i<4; ++i) memory[address+i] = uint8_t(value >> (i*8));
}
static void tests() {
    Layout l;
    require(decode_fvf(0x152, l) == 0 && l.stride == sizeof(WorldVertex));
    require(l.attributes[1].offset == offsetof(WorldVertex, normal));
    require(l.attributes[2].offset == offsetof(WorldVertex, diffuse));
    require(l.attributes[3].offset == offsetof(WorldVertex, uv));
    require(candidate_layout_supported(l));
    require(decode_fvf(0x252,l) == 0 && l.stride == 44 && candidate_layout_supported(l));
    require(decode_fvf(0x144, l) == 0 && l.stride == sizeof(ScreenVertex) && l.transformed);
    require(l.attributes[1].offset == offsetof(ScreenVertex, diffuse));
    require(l.attributes[2].offset == offsetof(ScreenVertex, uv));
    require(candidate_layout_supported(l));
    require(decode_fvf(0x402c2, l) == 0 && l.stride == sizeof(TwoTextureVertex));
    require(l.attributes[2].offset == offsetof(TwoTextureVertex, specular));
    require(l.attributes[4].offset == offsetof(TwoTextureVertex, uvw));
    require(!candidate_layout_supported(l));
    // Exhaust every texture dimension flag in each of eight locations.
    constexpr uint32_t size[4] = {8,12,16,4};
    for (uint32_t slot=0; slot<8; ++slot) for (uint32_t mode=0; mode<4; ++mode) {
        uint32_t fvf = 2 | ((slot+1)<<8) | (mode << (16+slot*2));
        require(decode_fvf(fvf, l) == 0);
        require(l.stride == 12+slot*8+size[mode]);
        require(l.attributes[slot+1].offset == 12+slot*8);
        require(l.attributes[slot+1].components * 4 == size[mode]);
    }
    for (uint32_t weights=1; weights<=5; ++weights) {
        require(decode_fvf(4+weights*2, l) == 0 && l.stride == 12+4*weights);
        require(!candidate_layout_supported(l));
        require(decode_fvf((4+weights*2)|0x1000, l) == 0 && l.stride == 12+4*weights);
        require(!candidate_layout_supported(l));
    }
    require(decode_fvf(0x22,l) == 0 && l.stride == 16 && !candidate_layout_supported(l));
    require(decode_fvf(0x4002,l) == 0 && l.stride == 16 && !candidate_layout_supported(l));
    Layout saved = l;
    for (uint32_t invalid : {0u, 1u, 0x16u|0x4000u, 0x2002u, 0x902u, 0x9006u, 0x1002u, 0x14u}) {
        require(decode_fvf(invalid,l) == invalid_call);
        require(l.stride == saved.stride && l.count == saved.count);
    }
    uint8_t memory[512]{};
    write32(memory,32,0x00401000); write32(memory,36,64);
    write32(memory,40,4); write32(memory,44,2);
    write32(memory,48,128); write32(memory,52,sizeof(ScreenVertex));
    DrawUP d{};
    require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == 0);
    require(d.vertex_count == 6 && d.required_bytes == 168 && d.next_esp == 56);
    require(d.return_address == 0x401000 && d.object == 64 && d.vertices == 128);
    write32(memory,52,32);  // native stride padding must not leak into packed upload
    require(decode_draw_up(memory,316,32,0x144,d) == 0 && d.required_bytes == 188);
    for (uint32_t i=0; i<6; ++i) {
        for (uint32_t j=0; j<28; ++j) memory[128+i*32+j] = uint8_t(i*28+j);
        if (i<5) std::memset(memory+128+i*32+28,0xee,4);
    }
    uint8_t upload[168]{};
    require(snapshot_draw_up(memory,316,d,upload,sizeof(upload)) == 0);
    for (uint32_t i=0; i<sizeof(upload); ++i) require(upload[i] == uint8_t(i));
    require(snapshot_draw_up(memory,316,d,upload,sizeof(upload)-1) == invalid_call);
    require(snapshot_draw_up(memory,315,d,upload,sizeof(upload)) == invalid_call);
    write32(memory,52,sizeof(ScreenVertex));
    require(!guest_range(512,0xfffffffe,4));
    require(!guest_range(1ull<<32,0xfffffffe,4));
    require(!guest_range(~uint64_t(0),1,~uint64_t(0)));
    require(!guest_range(~uint64_t(0),0xffffffff,~uint64_t(0)));
    require(!guest_range(512,513,0));
    require(guest_range(1ull<<32,0xffffffff,1));
    require(guest_range(512,500,12));
    require(decode_draw_up(memory,55,32,0x144,d) == invalid_call);
    for (uint32_t primitive=1; primitive<=6; ++primitive) {
        constexpr uint32_t expected[] = {0,2,4,3,6,4,4};
        write32(memory,40,primitive);
        require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == 0);
        require(d.vertex_count == expected[primitive]);
    }
    write32(memory,40,7);
    require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == invalid_call);
    write32(memory,40,4); write32(memory,44,0xffffffff);
    require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == invalid_call);
    write32(memory,52,0xffffffff);
    require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == invalid_call);
    write32(memory,44,0x55555556);
    require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == invalid_call);
    write32(memory,44,1); write32(memory,40,1);
    require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == 0 && d.required_bytes == 28);
    write32(memory,44,2);
    require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == invalid_call);
    DrawUP forged = d;
    forged.vertex_count = ~uint64_t(0);
    require(snapshot_draw_up(memory,sizeof(memory),forged,upload,sizeof(upload)) == invalid_call);
    forged = d; forged.stride = 0; forged.layout.stride = 0;
    require(snapshot_draw_up(memory,sizeof(memory),forged,upload,sizeof(upload)) == invalid_call);
    forged = d; forged.vertex_count = 0x100000000ull; forged.layout.stride = 4;
    require(snapshot_draw_up(memory,sizeof(memory),forged,upload,sizeof(upload)) == invalid_call);
    write32(memory,40,4);
    write32(memory,52,sizeof(ScreenVertex));
    write32(memory,44,2); write32(memory,48,0xfffffff0);
    require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == invalid_call);
    write32(memory,48,128); write32(memory,52,12);
    require(decode_draw_up(memory,sizeof(memory),32,0x144,d) == invalid_call);
    uint8_t rgba[4]; color_to_rgba(0x12345678,rgba);
    require(rgba[0]==0x34 && rgba[1]==0x56 && rgba[2]==0x78 && rgba[3]==0x12);
}
int main() {
#ifdef _WIN32
    static_assert(sizeof(void*) == 4, "Guest SDK oracle must be x86");
    static_assert(D3DFVF_XYZB2 == 8 && D3DFVF_SPECULAR == 0x80, "Windows SDK constants");
    static_assert(offsetof(IDirect3DDevice9Vtbl, DrawPrimitiveUP) == 83*4, "Guest draw vtable");
    static_assert(offsetof(IDirect3DDevice9Vtbl, SetFVF) == 89*4, "Guest FVF vtable");
    static_assert(offsetof(IDirect3DDevice9Vtbl, Clear) == 43*4, "Guest clear vtable");
    static_assert(offsetof(IDirect3D9Vtbl, CreateDevice) == 16*4, "Guest factory vtable");
    static_assert(sizeof(D3DLOCKED_RECT)==8 && sizeof(D3DVERTEXELEMENT9)==8, "Guest structures");
    static_assert(sizeof(D3DPRESENT_PARAMETERS)==56, "Guest present parameters");
    static_assert(D3DFVF_TEXCOORDSIZE3(1)==0x40000, "Texture flags from SDK");
#endif
    tests();
    std::printf("{\"checks\":%u,\"world_stride\":%zu,\"screen_stride\":%zu,\"two_texture_stride\":%zu}\n",
                checks,sizeof(WorldVertex),sizeof(ScreenVertex),sizeof(TwoTextureVertex));
}
