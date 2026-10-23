"""Keep the loopback game server independent of short-lived chat terminals."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8766/local-install.json"


def ready():
    try:
        with urllib.request.urlopen(URL, timeout=2) as response:
            return json.load(response)["folder"] == str(ROOT / "prepared")
    except (OSError, ValueError, KeyError):
        return False


if __name__ == "__main__":
    if ready():
        print("Game server already available at http://127.0.0.1:8766/")
    else:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        with (ROOT / "build/web-server.log").open("a", encoding="utf-8") as output, \
             (ROOT / "build/web-server-error.log").open("a", encoding="utf-8") as errors:
            process = subprocess.Popen(
                [str(ROOT / ".venv/Scripts/python.exe"), str(ROOT / "tools/serve_web_game.py"), "--port", "8766"],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                startupinfo=startup,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP |
                              subprocess.CREATE_BREAKAWAY_FROM_JOB,
            )
        (ROOT / "build/web-server.pid").write_text(str(process.pid), encoding="utf-8")
        for attempt in range(20):
            if ready():
                print("Game server available at http://127.0.0.1:8766/; PID", process.pid)
                break
            if process.poll() is not None:
                raise RuntimeError("Server exited; inspect build/web-server-error.log")
            time.sleep(0.25)
        else:
            raise RuntimeError("Server did not become available")
