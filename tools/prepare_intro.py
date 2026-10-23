"""Convert the installation's original intro movies for local browser playback."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required on PATH")
    output = ROOT / "build/intro-preview/media"
    output.mkdir(parents=True, exist_ok=True)
    clips = []
    for original, name in (("Logo.mpg", "logo.mp4"), ("GTAtitles.mpg", "titles.mp4")):
        source = ROOT / "original/movies" / original
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        target = output / name
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)], check=True)
        if hashlib.sha256(source.read_bytes()).hexdigest() != before:
            raise RuntimeError("Original movie changed during conversion")
        clips.append(dict(source=original, source_sha256=before, browser_file=name,
                          browser_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    (output.parent / "manifest.json").write_text(json.dumps(dict(original_files_modified=False,
        engine_execution=False, clips=clips), indent=2), encoding="utf-8")
    print("Original intro movies converted; this preview does not execute the game engine.")


if __name__ == "__main__":
    main()
