"""Exercise repeated startup against an actual HTTP server and OS file lock."""

import fcntl
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]


def test_launcher_reuses_existing_server(tmp_path):
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 8000)) == 0:
            pytest.skip("Port 8000 is already in use; stop the app to test startup")
    env = dict(os.environ, RPI_LAB_HOME=str(tmp_path), RPI_LAB_NO_BROWSER="1")
    with (tmp_path / "server.log").open("w+") as log:
        server = subprocess.Popen(
            ["bash", "scripts/start.sh"], cwd=PROJECT, env=env, stdout=log, stderr=log
        )
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:8000/api/instance", timeout=0.5
                    ) as response:
                        identity = json.load(response)
                    break
                except OSError:
                    if server.poll() is not None:
                        log.seek(0)
                        pytest.fail(log.read())
                    time.sleep(0.1)
            else:
                pytest.fail("Server failed to start")
            assert identity["runtime_directory"] == str(tmp_path)
            assert identity["pid"] == server.pid
            lock_contents = (tmp_path / "instance.lock").read_text()
            repeated = subprocess.run(
                ["bash", "scripts/start.sh"],
                cwd=PROJECT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert repeated.returncode == 0, repeated.stderr
            assert "already running" in repeated.stdout
            assert server.poll() is None
            assert (tmp_path / "instance.lock").read_text() == lock_contents
            # Direct duplicate uvicorn startup must also preserve lock-owner metadata.
            duplicate = subprocess.run(
                [
                    str(PROJECT / ".venv/bin/uvicorn"),
                    "backend.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8001",
                ],
                cwd=PROJECT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert duplicate.returncode != 0
            assert "Another lab instance" in duplicate.stderr
            assert (tmp_path / "instance.lock").read_text() == lock_contents
        finally:
            server.terminate()
            server.wait(timeout=10)
    # A remaining lock file without a living owner must not prevent restart.
    result = subprocess.run(
        [str(PROJECT / ".venv/bin/python"), "scripts/check_running.py"],
        cwd=PROJECT,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0


def test_busy_runtime_without_healthy_server(tmp_path):
    with (tmp_path / "instance.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(
            [str(PROJECT / ".venv/bin/python"), "scripts/check_running.py"],
            cwd=PROJECT,
            env=dict(os.environ, RPI_LAB_HOME=str(tmp_path)),
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 1
        assert "already in use" in result.stderr
        assert "Traceback" not in result.stderr
