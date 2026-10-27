"""Download the user-selected logo to a private cache for local launcher staging."""
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.pngmart.com/files/22/Grand-Theft-Auto-San-Andreas-Logo-PNG-Photo.png"
EXPECTED_SHA256 = "e3c54f3082f1e2461bb74b80d521c68a53cdaf07f6ec4ed0a748504fa83d507c"


def main():
    with urlopen(Request(URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as response:
        data = response.read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError("The selected logo download does not match the verified PNG")
    destination = ROOT / "build/launcher-assets/gta-sa-logo.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    print("Logo prepared locally. Run launcher staging to serve it.")


if __name__ == "__main__":
    main()
