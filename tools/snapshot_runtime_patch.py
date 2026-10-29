"""Save local runtime changes without changing the dependency's Git index."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "vendor/recomp-kit"


def pinned_base():
    """The commit the parent repository pins for the dependency.

    The dependency directory is a checkout that carries local modifications, and
    its own HEAD is not necessarily the published pin: a base commit re-created
    locally has a different hash even when its tree is equivalent (a Windows
    checkout differs only by file modes and line endings). The gitlink in the
    parent index is what a consumer clones, so that is the commit the patch is
    recorded against.
    """
    result = subprocess.run(["git", "ls-tree", "HEAD", "--", "vendor/recomp-kit"],
                            cwd=ROOT, capture_output=True)
    fields = result.stdout.decode().split()
    if result.returncode == 0 and len(fields) >= 3 and fields[0] == "160000":
        return fields[2]
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=KIT).decode().strip()


base = pinned_base()
patch = subprocess.check_output(["git", "diff", "--binary", "HEAD", "--"], cwd=KIT)
untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=KIT)
allowed = {".cpp", ".h", ".py", ".js", ".md", ".cmake", ".txt"}
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
