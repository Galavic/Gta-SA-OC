"""Stored PE bytes are data of the containing image, not mapped DLL code."""
from pathlib import Path
import struct
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
import translate as T


def test_declared_file_data_stays_readable_and_other_code_stays_executable():
    base, stored, code = 0x00400000, 0x00401000, 0x00401100
    image = synthetic_image({stored: b"MZ\x12\x34", code: bytes.fromhex("b8 01 00 00 00 c3")})
    before = image.data
    image.declare_data_regions([(stored, stored + 0x40)])
    assert image.data == before
    assert image.rd32(stored) == 0x34125A4D
    assert not image.is_exec(stored)
    assert image.is_exec(stored - 1) and image.is_exec(stored + 0x40)
    assert image.is_exec(code)


def test_pointers_stored_in_an_embedded_image_do_not_create_parent_entries():
    stored, code = 0x00401000, 0x00401100
    image = synthetic_image({stored: struct.pack("<I", code), code: b"\xc3"})
    image.data_ranges = [(stored, stored + 0x40, ".data")]
    image.declare_data_regions([(stored, stored + 0x40)])
    starts, interior = image.code_pointers({code})
    assert code not in starts and code not in interior


def test_bad_declarations_cannot_mask_bytes_outside_the_guest_image():
    image = synthetic_image({0x00401000: b"\xc3"})
    with pytest.raises(T.TranslateError):
        image.declare_data_regions([(image.base - 1, image.base + 0x100)])


def test_many_overlapping_data_ranges_preserve_exclusive_code_boundaries():
    image = synthetic_image({0x00401000: b"\xc3"})
    ranges = [(0x00401010 + i * 7, 0x00401013 + i * 7) for i in range(128)]
    ranges += [(0x00401011, 0x00401012), (0x0040100F, 0x00401011)]
    image.declare_data_regions(ranges)
    assert image.is_exec(0x0040100E)
    assert not image.is_exec(0x0040100F)
    assert not image.is_exec(0x00401012)
    assert image.is_exec(0x00401013)
    for lo, hi in ranges:
        assert image.is_declared_data(lo) and image.is_declared_data(hi - 1)
        assert not image.is_exec(lo) and not image.is_exec(hi - 1)
    assert image.is_exec(0x00401013 + 127 * 7)
