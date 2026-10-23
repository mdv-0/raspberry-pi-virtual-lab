#!/usr/bin/env python3
"""Exit 10 for a healthy existing instance, 0 if free, 1 if occupied/unhealthy."""

import fcntl
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "http://127.0.0.1:8000"
PROJECT = Path(__file__).resolve().parents[1]


def main() -> int:
    home = Path(os.environ.get("RPI_LAB_HOME", PROJECT / "runtime")).resolve()
    lock_path = home / "instance.lock"
    if not lock_path.exists():
        return 0
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return 0
        except BlockingIOError:
            try:
                with urllib.request.urlopen(
                    URL + "/api/instance", timeout=3
                ) as response:
                    instance = json.load(response)
                if instance.get(
                    "application"
                ) == "raspberry-pi-virtual-lab" and instance.get(
                    "runtime_directory"
                ) == str(home):
                    print(
                        f"Virtual Lab is already running at {URL} (PID {instance['pid']})."
                    )
                    return 10
            except (OSError, ValueError, KeyError):
                pass
            print(
                f"Runtime {home} is already in use, but its server could not be verified at {URL}. Wait for startup or stop the existing server before retrying. Do not delete instance.lock.",
                file=sys.stderr,
            )
            return 1


if __name__ == "__main__":
    sys.exit(main())
