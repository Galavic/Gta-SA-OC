"""Verify the isolated executable and availability of original story resources."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
variant = ROOT / "variants/singleplayer"
preparation = json.loads((variant / "preparation.json").read_text(encoding="utf-8"))
source = Path(preparation["installation"])
image = variant / "prepared/gta_sa.exe"
digest = hashlib.sha256(image.read_bytes()).hexdigest()
assert digest == preparation["source_sha256"], "Prepared image identity changed"
candidates = [source / "gta_sa.exe", Path(preparation["source_image"])]
matching_source = next((candidate for candidate in candidates if candidate.is_file()
                       and hashlib.sha256(candidate.read_bytes()).hexdigest() == digest), None)
assert matching_source is not None, "No installed executable matches the prepared image"
names = ["data/script/main.scm", "data/script/script.img", "anim/cuts.img",
         "anim/ped.ifp", "movies/Logo.mpg", "movies/GTAtitles.mpg"]
resources = [{"file": name, "exists": (source / name).is_file(),
              "bytes": (source / name).stat().st_size if (source / name).is_file() else 0}
             for name in names]
report = dict(image_sha256=digest, current_source_image=str(matching_source),
              installed_image_matches_prepared=True,
              original_resources=resources, original_entry_verified=False,
              original_intro_verified=False, first_mission_verified=False,
              playable_verified=False)
(variant / "original-engine-acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
for resource in resources:
    print(resource["file"], "available" if resource["exists"] else "MISSING", resource["bytes"])
print("Executable identity verified; gameplay remains unverified.")
