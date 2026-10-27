"""Create a private CSS font from the user's decoded menu atlas and metrics."""
import json
from pathlib import Path
import struct
import sys
import zlib

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


def build(directory):
    metadata = json.loads((directory / "metrics.json").read_text())
    png = (directory / "font2.png").read_bytes()
    position, compressed = 8, []
    while position < len(png):
        length = struct.unpack_from(">I", png, position)[0]
        kind = png[position + 4:position + 8]
        data = png[position + 8:position + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack_from(">II", data)
            if data[8:10] != bytes([8, 6]):
                raise ValueError("Expected exported 8-bit RGBA atlas")
        if kind == b"IDAT":
            compressed.append(data)
        position += length + 12
    pixels = zlib.decompress(b"".join(compressed))
    stride = width * 4 + 1
    if any(pixels[y * stride] != 0 for y in range(height)):
        raise ValueError("Expected exporter PNG with unfiltered rows")

    def alpha(x, y):
        return pixels[y * stride + 1 + x * 4 + 3] >= 96

    cells = {item["id"]: item for item in metadata["glyphs"]}
    bounds = []
    for cell in cells.values():
        if cell["id"] == 0:
            continue
        bounds.extend(y for y in range(cell["height"]) for x in range(cell["width"])
                      if alpha(cell["x"] + x, cell["y"] + y))
    top, bottom = min(bounds), max(bounds)
    scale = 700 / (bottom - top + 1)
    glyphs, metrics = {}, {}
    pen = TTGlyphPen(None)
    glyphs[".notdef"] = pen.glyph()
    metrics[".notdef"] = (500, 0)
    for identifier, cell in cells.items():
        pen = TTGlyphPen(None)
        if identifier != 0:
            # Merge horizontal runs. Consistent winding preserves holes between
            # strips while retaining the original raster's letter silhouettes.
            for y in range(cell["height"]):
                x = 0
                while x < cell["width"]:
                    if not alpha(cell["x"] + x, cell["y"] + y):
                        x += 1
                        continue
                    start = x
                    while x < cell["width"] and alpha(cell["x"] + x, cell["y"] + y):
                        x += 1
                    left, right = round(start * scale), round(x * scale)
                    low, high = round((bottom - y) * scale), round((bottom - y + 1) * scale)
                    pen.moveTo((left, low))
                    pen.lineTo((left, high))
                    pen.lineTo((right, high))
                    pen.lineTo((right, low))
                    pen.closePath()
        name = f"cell{identifier}"
        glyphs[name] = pen.glyph()
        metrics[name] = (round((metadata["widths"][0][identifier] or 16) * scale), 0)
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(list(glyphs))
    builder.setupCharacterMap({item["code"]: f"cell{item['id']}" for item in metadata["glyphs"]})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=900, descent=-200)
    builder.setupNameTable({"familyName": "Local SA Menu", "styleName": "Regular",
                            "uniqueFontIdentifier": "LocalSAMenu-1", "fullName": "Local SA Menu",
                            "psName": "LocalSAMenu", "version": "Version 1.0"})
    builder.setupOS2(sTypoAscender=900, sTypoDescender=-200, usWinAscent=1000, usWinDescent=200)
    builder.setupPost()
    builder.save(directory / "menu.ttf")
    print("Prepared private CSS font from local San Andreas glyphs")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
