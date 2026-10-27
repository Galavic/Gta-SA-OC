"""Input reconciliation tests with synthetic bytes, never game assets."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tomllib

import pytest

spec = importlib.util.spec_from_file_location(
    "apply_contracts", Path(__file__).parents[2] / "tools/apply_call_thunk_contracts.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


@pytest.mark.parametrize("array", [
    "[0x1000]",
    "[\n    0x1000,\n]",
    "[0x1000,\n # CALL [ESI+0x24] is evidence, not the array end.\n 0x2000] # end",
])
def test_rewrite_accepts_inline_end_and_comment_brackets(array):
    source = "[translate]\nentry_points = " + array + "\nanimation_counter = 0\n"
    result = sync.rewrite_entries(source, {0x1000, 0x3000})
    parsed = tomllib.loads(result)["translate"]
    assert parsed["entry_points"] == [0x1000, 0x3000]
    assert parsed["animation_counter"] == 0


def fixture_inputs(root):
    data = b"synthetic executable identity"
    identity = hashlib.sha256(data).hexdigest()
    (root / "image").write_bytes(data)
    config = ('[game]\ndeveloper_exe = "image"\nsha256 = "' + identity + '"\n'
              '[translate]\nentry_points = [0x1000]\n'
              'no_fallthrough_calls_file = "calls.json"\n')
    (root / "game.toml").write_text(config)
    (root / "calls.json").write_text("[16]\n")
    report = {"executable_sha256": identity, "contracts": [
        {"call_site": 32, "changed_continuation": 0x2000, "destination": 0x3000}]}
    (root / "audit.json").write_text(json.dumps(report))
    return config, report


def test_merge_is_idempotent_and_preserves_original_backup(tmp_path):
    original, _ = fixture_inputs(tmp_path)
    sync.apply_contracts(tmp_path, tmp_path / "audit.json", [0x4000])
    first = (tmp_path / "game.toml").read_bytes()
    sync.apply_contracts(tmp_path, tmp_path / "audit.json", [0x4000])
    assert (tmp_path / "game.toml").read_bytes() == first
    assert (tmp_path / "game.toml.before-allbytes").read_text() == original
    assert json.loads((tmp_path / "calls.json").read_text()) == [16, 32]
    assert tomllib.loads(first.decode())["translate"]["entry_points"] == [
        0x1000, 0x2000, 0x3000, 0x4000]


def test_wrong_identity_leaves_both_inputs_unchanged(tmp_path):
    original, report = fixture_inputs(tmp_path)
    report["executable_sha256"] = "0" * 64
    (tmp_path / "audit.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="identities differ"):
        sync.apply_contracts(tmp_path, tmp_path / "audit.json")
    assert (tmp_path / "game.toml").read_text() == original
    assert (tmp_path / "calls.json").read_text() == "[16]\n"
    assert not (tmp_path / "game.toml.before-allbytes").exists()


def test_observed_entries_reject_another_executable(tmp_path):
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({"executable_sha256": "verified", "entries": ["0x1000", 8192]}))
    assert sync.load_entries(path, "verified") == [4096, 8192]
    with pytest.raises(ValueError, match="identities differ"):
        sync.load_entries(path, "other")
