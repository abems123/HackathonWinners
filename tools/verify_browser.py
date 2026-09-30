"""Run browser smoke checks on an isolated, disposable synthetic database."""

import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent


def run():
    with tempfile.TemporaryDirectory(prefix="bron-browser-") as directory:
        database = Path(directory) / "demo.sqlite3"
        env = {
            **os.environ,
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
            "DJANGO_DEBUG": "True",
            "DATABASE_URL": "sqlite:///" + database.as_posix(),
            "AI_MODE": "cache",
            "GEMINI_MODEL": "",
        }
        for command in ["migrate", "seed"]:
            subprocess.run(
                [sys.executable, "manage.py", command, "--verbosity", "0"],
                cwd=ROOT,
                env=env,
                check=True,
            )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        with open(Path(directory) / "server.log", "w", encoding="utf-8") as log:
            server = subprocess.Popen(
                [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("The isolated test server exited before startup.")
                    try:
                        with urlopen(url + "/login/", timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("The isolated browser server did not start.")
                subprocess.run(
                    [sys.executable, "tools/browser_smoke.py"],
                    cwd=ROOT,
                    env={**env, "BRON_TEST_URL": url},
                    check=True,
                )
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == "__main__":
    run()
