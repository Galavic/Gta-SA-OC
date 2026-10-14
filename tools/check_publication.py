"""Inspect staged publication inputs without printing possible credentials."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
entries = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=ROOT).decode().split("\0")
blocked_dirs = {"analysis", "build", "variants", "original", "prepared", ".venv", ".clyra", ".pytest_cache", "__pycache__"}
blocked_ext = {".exe", ".dll", ".wasm", ".img", ".txd", ".dff", ".ifp", ".scm", ".mpg", ".wav", ".bin", ".o", ".obj", ".pyc", ".zip", ".pem", ".key"}
credentials = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{30,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)")
errors = []
count = 0
total = 0
for entry in filter(None, entries):
    metadata, name = entry.split("\t", 1)
    mode, object_id, _ = metadata.split()
    if mode == "160000":
        assert name == "vendor/recomp-kit"
        continue
    if Path(name).parts[0] in blocked_dirs or Path(name).suffix.lower() in blocked_ext:
        errors.append(f"Private input or binary staged: {name}")
    data = subprocess.check_output(["git", "cat-file", "blob", object_id], cwd=ROOT)
    if len(data) > 2_000_000 or b"\0" in data:
        errors.append(f"Unexpected large or binary file staged: {name}")
    if credentials.search(data):
        errors.append(f"Possible credential staged: {name}")
    if re.search(rb"C:[/\\]Users[/\\][^/\\\s\"']+[/\\]", data):
        errors.append(f"Personal absolute path staged: {name}")
    if Path(name).suffix == ".md":
        text = re.sub(r"```.*?```", "", data.decode("utf-8"), flags=re.S)
        text = re.sub(r"`[^`\n]*`", "", text)
        for target in re.findall(r"\]\(([^)]+)\)", text):
            target = target.split("#", 1)[0].split("?", 1)[0].strip("<>")
            if target and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                if not (ROOT / name).parent.joinpath(target).exists():
                    errors.append(f"Broken documentation link: {name} -> {target}")
    count += 1
    total += len(data)
if errors:
    raise SystemExit("\n".join(errors))
print(f"Publication checks passed: {count} source/documentation files, {total} bytes, one pinned dependency.")
