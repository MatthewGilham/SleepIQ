"""Exercise process ownership with synthetic HTTP on an ephemeral loopback port."""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def test_duplicate_listener_cannot_replace_original() -> None:
    root = Path(__file__).resolve().parents[2]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--app-dir",
        "backend",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
    ]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    address = f"http://127.0.0.1:{port}/api/v1/health"
    first = subprocess.Popen(
        command, cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags
    )
    second = None
    try:
        deadline = time.monotonic() + 10
        while True:
            if first.poll() is not None:
                raise AssertionError("Test listener exited before startup")
            try:
                with opener.open(address, timeout=1) as response:
                    assert response.status == 200
                break
            except (urllib.error.URLError, TimeoutError):
                if time.monotonic() > deadline:
                    raise AssertionError("Test listener did not become ready") from None
                time.sleep(0.05)
        second = subprocess.Popen(
            command,
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        assert second.wait(timeout=10) != 0
        assert first.poll() is None
        with opener.open(address, timeout=1) as response:
            assert response.status == 200
    finally:
        # These handles refer only to children created by this test. Never use PID lookup.
        for owned in (second, first):
            if owned is not None:
                if owned.poll() is None:
                    owned.terminate()
                owned.wait(timeout=10)
