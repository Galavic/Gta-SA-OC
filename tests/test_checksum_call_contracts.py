"""Reject changes that invalidate the exact native checksum control proof."""
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor/recomp-kit/tools/recomp"))
import translate as T
import audit_checksum_call_thunks as A

SITE, CALLEE = 0x00fd63b5, 0x00fd63c1


@pytest.fixture
def image():
    path = ROOT / "prepared/gta_sa.exe"
    if not path.is_file():
        pytest.skip("Requires the user's original local executable")
    return T.Image(str(path))


def replace(image, address, data):
    offset = address-image.base
    image.data = image.data[:offset]+data+image.data[offset+len(data):]


def test_original_checksum_shape_proves_bounded_destination(image):
    row = A.inspect(image, SITE, CALLEE)
    assert row["metadata"] == SITE+6
    assert row["changed_continuation"] == 0x00fd6466
    assert row["checksum_form"]["words"] == 78
    assert row["destination"] == 0x00ef3560


def test_different_loop_edge_cannot_admit_the_contract(image):
    replace(image, 0x00fd6448, b"\xe8")
    assert A.inspect(image, SITE, CALLEE) is None


def test_different_read_stride_cannot_admit_the_contract(image):
    replace(image, 0x00fd6441, b"\x08")
    assert A.inspect(image, SITE, CALLEE) is None


def test_zero_word_count_is_a_full_wrap_loop_not_an_empty_checksum(image):
    replace(image, 0x00fd6419, b"\x00\x00")
    assert A.inspect(image, SITE, CALLEE) is None


def test_loop_can_return_through_original_neutral_prefix(image):
    row = A.inspect(image, 0x00F97ADF, 0x00F97AEC)
    assert row is not None
    assert row["checksum_form"]["words"] == 56


@pytest.mark.parametrize("destination", [0x00F97B59, 0x00F97B5D])
def test_loop_cannot_reset_accumulator_or_enter_operand_bytes(image, destination):
    # Actual short JNE at f97b74; these targets respectively re-zero the
    # accumulator or enter the displacement of the checksum load.
    replace(image, 0x00F97B75, bytes([(destination-0x00F97B76) & 0xff]))
    assert A.inspect(image, 0x00F97ADF, 0x00F97AEC) is None
