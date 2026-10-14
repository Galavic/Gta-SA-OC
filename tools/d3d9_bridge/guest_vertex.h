#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

// Windows guest values, deliberately independent of the candidate's d3d9.h.
namespace gtasa_d3d9 {
constexpr uint32_t invalid_call = 0x8876086c;
enum class Semantic { Position, BlendWeights, BlendIndices, Normal, PointSize,
                      Diffuse, Specular, Texcoord };
struct Attribute {
    Semantic semantic;
    uint32_t offset, components, index;
    bool packed_color;
};
struct Layout {
    Attribute attributes[15]{};
    uint32_t count = 0, stride = 0;
    bool transformed = false;
};

inline uint32_t decode_fvf(uint32_t fvf, Layout& result) {
    Layout out;
    auto add = [&](Semantic semantic, uint32_t components, uint32_t index = 0,
                   bool color = false) {
        out.attributes[out.count++] = {semantic, out.stride, components, index, color};
        out.stride += color ? 4 : components * 4;
    };
    // Reserved bits, mutually exclusive last-beta representations, texture count.
    if ((fvf & 0x2001) || ((fvf & 0x9000) == 0x9000) || ((fvf >> 8) & 15) > 8)
        return invalid_call;
    uint32_t position = fvf & 0x400e;
    uint32_t betas = 0;
    if (position == 2) add(Semantic::Position, 3);
    else if (position == 4 || position == 0x4002) {
        add(Semantic::Position, 4);
        out.transformed = position == 4;
    } else if (position >= 6 && position <= 14 && !(position & 1)) {
        add(Semantic::Position, 3);
        betas = (position - 4) / 2;
    } else return invalid_call;
    bool indices = (fvf & 0x9000) != 0;
    if (indices && !betas) return invalid_call;
    if (betas > uint32_t(indices)) add(Semantic::BlendWeights, betas - uint32_t(indices));
    if (indices) add(Semantic::BlendIndices, 4, 0, true);
    if (fvf & 0x10) {
        if (out.transformed) return invalid_call;
        add(Semantic::Normal, 3);
    }
    if (fvf & 0x20) add(Semantic::PointSize, 1);
    if (fvf & 0x40) add(Semantic::Diffuse, 4, 0, true);
    if (fvf & 0x80) add(Semantic::Specular, 4, 0, true);
    constexpr uint32_t dimensions[4] = {2, 3, 4, 1};
    for (uint32_t i = 0; i < ((fvf >> 8) & 15); ++i)
        add(Semantic::Texcoord, dimensions[(fvf >> (16 + 2*i)) & 3], i);
    result = out;
    return 0;
}

// Layout acceptance only; not a claim of complete renderer compatibility.
inline bool candidate_layout_supported(const Layout& layout) {
    for (uint32_t i = 0; i < layout.count; ++i) {
        const auto& a = layout.attributes[i];
        if (a.semantic == Semantic::BlendWeights || a.semantic == Semantic::BlendIndices ||
            a.semantic == Semantic::Specular || a.semantic == Semantic::PointSize ||
            (a.semantic == Semantic::Texcoord && (a.index > 1 || a.components != 2)) ||
            (a.semantic == Semantic::Position && a.components == 4 && !layout.transformed))
            return false;
    }
    return true;
}
inline bool guest_range(uint64_t memory_size, uint32_t address, uint64_t length) {
    const uint64_t guest_limit = uint64_t(1) << 32;
    return uint64_t(address) <= memory_size &&
           length <= memory_size - uint64_t(address) &&
           length <= guest_limit - uint64_t(address);
}
inline uint32_t read32(const uint8_t* memory, uint32_t address) {
    return uint32_t(memory[address]) | uint32_t(memory[address+1]) << 8 |
           uint32_t(memory[address+2]) << 16 | uint32_t(memory[address+3]) << 24;
}
struct DrawUP {
    uint32_t object, primitive, primitive_count, vertices, stride;
    uint32_t return_address, next_esp;
    uint64_t vertex_count, required_bytes;
    Layout layout;
};

// Guest COM stdcall: return, this, PrimitiveType, PrimitiveCount, data, stride.
// No host pointer cast and no CPU mutation before full validation.
inline uint32_t decode_draw_up(const uint8_t* memory, uint64_t memory_size,
                              uint32_t esp, uint32_t fvf, DrawUP& result) {
    if (!memory || !guest_range(memory_size, esp, 24) || esp > 0xffffffe7)
        return invalid_call;
    DrawUP out{};
    out.return_address = read32(memory, esp);
    out.object = read32(memory, esp+4);
    out.primitive = read32(memory, esp+8);
    out.primitive_count = read32(memory, esp+12);
    out.vertices = read32(memory, esp+16);
    out.stride = read32(memory, esp+20);
    out.next_esp = esp+24;
    if (!out.object || !guest_range(memory_size, out.object, 4) ||
        decode_fvf(fvf, out.layout) || out.stride < out.layout.stride)
        return invalid_call;
    uint64_t n = out.primitive_count;
    switch (out.primitive) {
    case 1: out.vertex_count = n; break;       // POINTLIST
    case 2: out.vertex_count = 2*n; break;     // LINELIST
    case 3: out.vertex_count = n ? n+1 : 0; break;
    case 4: out.vertex_count = 3*n; break;     // TRIANGLELIST
    case 5: case 6: out.vertex_count = n ? n+2 : 0; break;
    default: return invalid_call;
    }
    if (out.vertex_count && out.vertex_count-1 > (uint64_t(1)<<32)/out.stride)
        return invalid_call;
    out.required_bytes = out.vertex_count ?
        (out.vertex_count-1)*out.stride + out.layout.stride : 0;
    if ((out.vertex_count && !out.vertices) ||
        !guest_range(memory_size, out.vertices, out.required_bytes))
        return invalid_call;
    result = out;
    return 0;
}
// Candidate UP copies vertex_count*stride bytes, including final padding.
// Stage tightly packed bytes so it cannot read beyond the last actual attribute.
// Keep original BGRA DWORD colors: candidate UP already swaps red and blue.
inline uint32_t snapshot_draw_up(const uint8_t* memory, uint64_t memory_size,
                                const DrawUP& draw, uint8_t* destination,
                                uint64_t destination_size) {
    if (!draw.layout.stride || draw.stride < draw.layout.stride ||
        draw.vertex_count > (uint64_t(1)<<32)/draw.layout.stride ||
        (draw.vertex_count && draw.vertex_count-1 > (uint64_t(1)<<32)/draw.stride))
        return invalid_call;
    uint64_t packed_size = draw.vertex_count * draw.layout.stride;
    uint64_t required = draw.vertex_count ?
        (draw.vertex_count-1)*draw.stride+draw.layout.stride : 0;
    const uint64_t host_size_limit = uint64_t(~size_t(0));
    if (packed_size > host_size_limit || required > host_size_limit ||
        !memory || (packed_size && !destination) ||
        packed_size > destination_size || !guest_range(memory_size, draw.vertices, required))
        return invalid_call;
    for (uint64_t i=0; i<draw.vertex_count; ++i)
        std::memcpy(destination+i*draw.layout.stride,
                    memory+draw.vertices+i*draw.stride, draw.layout.stride);
    return 0;
}
inline void color_to_rgba(uint32_t argb, uint8_t rgba[4]) {
    rgba[0] = uint8_t(argb >> 16); rgba[1] = uint8_t(argb >> 8);
    rgba[2] = uint8_t(argb); rgba[3] = uint8_t(argb >> 24);
}
} // namespace gtasa_d3d9
