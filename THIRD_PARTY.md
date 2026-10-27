# Dependencies and attribution

## Project attribution

[Galavic](https://github.com/Galavic) is the principal contributor and project
lead for GTA SA OC. This credit applies to this project's work; dependencies
and original game materials retain the authorship and notices listed below.

## Upstream projects and tools

- [recomp-kit](https://github.com/veritr1x/recomp-kit), revision
  `eb32cc42623e0e9e868b9d27423a57d5a5cba56b`, is an upstream dependency,
  not work authored by this project. Its handwritten implementation is MIT
  licensed. Its own LICENSE and NOTICE remain in the submodule; the runtime
  patch's license is also preserved under patches/RECOMP_KIT_LICENSE.
- Ghidra, Capstone, pefile, Unicorn, CMake, Ninja and Emscripten are external
  tools and retain their respective upstream licenses.
- gta-reversed and SanAndreasUnity are references evaluated during the work.
  They are not distributed as game assets or presented as a complete port.
- GTA San Andreas executables, data, artwork, audio, levels and generated
  translations retain their original ownership. They are not included here.
- The local recreation uses Three.js 0.160.0 and three-mesh-bvh 0.7.8.
  Their MIT licenses are preserved in `web/recreation/public/vendor/`.
  The recreation code was continued from the user's local Three.js prototype;
  its game-derived interface and audio exports remain ignored local files.

The documentation records source provenance, test scope and limitations.
No project-wide license is assigned to materials owned by third parties.

## Social profile logos

The launcher uses original X, GitHub, Discord and WhatsApp SVG assets served
locally. Logo ownership, official download sources and retrieval date are
documented in [social icon sources](tools/web/launcher/social-icons/SOURCES.md).
