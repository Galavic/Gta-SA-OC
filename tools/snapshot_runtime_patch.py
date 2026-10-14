"""Save local runtime changes without changing the dependency's Git index."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "vendor/recomp-kit"
base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=KIT).decode().strip()
patch = subprocess.check_output(["git", "diff", "--binary", "HEAD", "--"], cwd=KIT)
untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=KIT)
allowed = {".cpp", ".h", ".py", ".md", ".cmake", ".txt"}
for name in untracked.decode().split("\0"):
    if not name:
        continue
    source = KIT / name
    if source.suffix.lower() not in allowed or source.stat().st_size > 2_000_000:
        raise ValueError(f"Review untracked dependency file before publishing: {name}")
    result = subprocess.run(["git", "diff", "--no-index", "--binary", "--", "/dev/null", name],
                            cwd=KIT, capture_output=True)
    if result.returncode != 1:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    patch += result.stdout
(ROOT / "patches/current-vendor.patch").write_bytes(patch)
(ROOT / "patches/recomp-kit-base.txt").write_text(base + "\n", encoding="utf-8")
print(f"Saved runtime patch against {base}: {len(patch)} bytes")
