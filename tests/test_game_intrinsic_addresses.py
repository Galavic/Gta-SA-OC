"""An unrelated executable must execute code at the kit's legacy addresses."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/recomp-kit/tools/recomp/tests"))
from test_translate_driver import synthetic_image
from test_translate_insns import Opts
import translate as T


@pytest.fixture
def disabled_legacy(monkeypatch):
    monkeypatch.setattr(T, "INTRINSIC_BODY", dict(T.INTRINSIC_BODY))
    T.configure_legacy_intrinsics(False)


@pytest.mark.parametrize("address", [T.INTRINSIC_SETJMP, T.INTRINSIC_LONGJMP])
def test_unrelated_original_function_is_emitted(disabled_legacy, address):
    image = synthetic_image({address: bytes.fromhex("b8 07 00 00 00 c3")}, base=address - 0x1000)
    fn = T.Function(address, "actual_guest_function", 6, image.recover(address, set()))
    fn.measure(image)
    translator = T.Translator(image, {address}, Opts())
    translator.prepare(fn)
    code = "\n".join(translator.translate(fn))
    assert "c->r[0] = 0x7u" in code
    assert "recomp_setjmp" not in code and "recomp_longjmp" not in code


def test_direct_call_does_not_create_host_setjmp(disabled_legacy):
    start, target = 0x00401000, T.INTRINSIC_SETJMP
    displacement = (target - start - 5).to_bytes(4, "little", signed=True)
    image = synthetic_image({start: b"\xe8" + displacement + b"\xc3", target: b"\xc3"},
                            size=target - 0x00400000 + 0x1000)
    fn = T.Function(start, "ordinary_call", 6, image.recover(start, {target}))
    fn.measure(image)
    translator = T.Translator(image, {start, target}, Opts())
    translator.prepare(fn)
    code = "\n".join(translator.translate(fn))
    assert f"CALL_FN({target:08x})" in code
    assert "setjmp" not in code


def test_legacy_configuration_can_be_restored(monkeypatch):
    monkeypatch.setattr(T, "INTRINSIC_BODY", dict(T.INTRINSIC_BODY))
    T.configure_legacy_intrinsics(False)
    T.configure_legacy_intrinsics(True)
    assert T.INTRINSIC_BODY == T.LEGACY_INTRINSIC_BODY
