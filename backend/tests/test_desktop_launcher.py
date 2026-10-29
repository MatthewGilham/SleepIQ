"""Launcher helpers and shortcut creator against throwaway loopback servers; no real browser or Desktop."""

import json
import os
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def serve(body: dict[str, str], delay: float = 0) -> tuple[HTTPServer, int]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=lambda: (time.sleep(delay), server.serve_forever()), daemon=True).start()
    return server, server.server_address[1]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def ps(command: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT, env={**os.environ, **env}, capture_output=True, text=True, check=False,
        timeout=90, creationflags=subprocess.CREATE_NO_WINDOW,
    )


def run_script(name: str, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-File", str(ROOT / "scripts" / name), *args],
        cwd=ROOT, env={**os.environ, **env}, capture_output=True, text=True, check=False,
        timeout=90, creationflags=subprocess.CREATE_NO_WINDOW,
    )


def test_running_check_accepts_only_a_sleepiq_health_answer():
    good, good_port = serve({"status": "ok"})
    other, other_port = serve({"status": "bad"})
    try:
        out = ps(
            f". ./scripts/launcher-tools.ps1; Test-SleepIQRunning {good_port}; "
            f"Test-SleepIQRunning {other_port}; Test-SleepIQRunning {free_port()}"
        )
    finally:
        good.shutdown()
        other.shutdown()
    assert out.stdout.split() == ["True", "False", "False"], out.stderr


def test_wait_succeeds_when_the_server_appears_and_gives_up_otherwise():
    late, port = serve({"status": "ok"}, delay=2)
    try:
        out = ps(f". ./scripts/launcher-tools.ps1; Wait-SleepIQReady {port} 20")
    finally:
        late.shutdown()
    assert out.stdout.split() == ["True"], out.stderr
    started = time.monotonic()
    out = ps(f". ./scripts/launcher-tools.ps1; Wait-SleepIQReady {free_port()} 2")
    assert out.stdout.split() == ["False"] and time.monotonic() - started < 15


def test_already_running_opens_browser_without_starting_a_second_copy(tmp_path):
    running, port = serve({"status": "ok"})
    marker, log = tmp_path / "started", tmp_path / "browser.log"
    fake = tmp_path / "fake-start.ps1"
    fake.write_text(f"Set-Content '{marker.as_posix()}' 'started'", encoding="utf-8")
    try:
        result = run_script(
            "launch.ps1", "-Port", str(port), "-StartScript", str(fake), "-NoPause",
            SLEEPIQ_TEST_BROWSER_LOG=str(log),
        )
    finally:
        running.shutdown()
    assert result.returncode == 0, result.stderr
    assert log.read_text().split() == [f"http://127.0.0.1:{port}"]
    assert not marker.exists()


def test_cold_start_opens_browser_only_after_the_app_answers(tmp_path):
    port, log = free_port(), tmp_path / "browser.log"
    fake = tmp_path / "fake-start.ps1"
    # Stand-in app: answers the health check after ~3 s, for ~8 s, then exits like Ctrl+C would.
    fake.write_text(
        "$s = New-Object Net.HttpListener; "
        f"$s.Prefixes.Add('http://127.0.0.1:{port}/'); Start-Sleep 3; $s.Start(); "
        "$end = [DateTime]::UtcNow.AddSeconds(8); "
        "while ([DateTime]::UtcNow -lt $end) { "
        "  $t = $s.GetContextAsync(); "
        "  if ($t.Wait(500)) { $b = [Text.Encoding]::UTF8.GetBytes('{\"status\":\"ok\"}'); "
        "    $t.Result.Response.OutputStream.Write($b, 0, $b.Length); $t.Result.Response.Close() } }; $s.Stop()",
        encoding="utf-8",
    )
    result = run_script(
        "launch.ps1", "-Port", str(port), "-StartScript", str(fake), "-NoPause",
        SLEEPIQ_TEST_BROWSER_LOG=str(log),
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Keep this window open" in result.stdout
    assert log.read_text().split() == [f"http://127.0.0.1:{port}"]


def test_failed_start_reports_and_opens_nothing(tmp_path):
    log = tmp_path / "browser.log"
    fake = tmp_path / "fake-start.ps1"
    fake.write_text("throw 'Build the frontend first'", encoding="utf-8")
    result = run_script(
        "launch.ps1", "-Port", str(free_port()), "-StartScript", str(fake),
        "-ReadyTimeoutSeconds", "2", "-NoPause", SLEEPIQ_TEST_BROWSER_LOG=str(log),
    )
    assert result.returncode == 1
    assert "could not start" in result.stdout and "Build the frontend first" in result.stdout
    time.sleep(3)
    assert not log.exists()


def read_shortcut(link: Path) -> tuple[str, str, str]:
    out = ps(
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{link}'); "
        "Write-Output $s.TargetPath; Write-Output $s.Arguments; Write-Output $s.WorkingDirectory"
    )
    target, arguments, folder = out.stdout.strip().splitlines()
    return target, arguments, folder


def test_shortcut_points_at_the_launcher_and_never_overwrites_silently(tmp_path):
    first = run_script("install-shortcut.ps1", "-Folder", str(tmp_path))
    assert first.returncode == 0, first.stderr
    target, arguments, folder = read_shortcut(tmp_path / "SleepIQ.lnk")
    assert target.lower().endswith("powershell.exe")
    assert arguments == f'-NoProfile -File "{ROOT / "scripts" / "launch.ps1"}"'
    assert Path(folder) == ROOT
    assert "ExecutionPolicy" not in arguments and "Bypass" not in arguments
    assert run_script("install-shortcut.ps1", "-Folder", str(tmp_path)).returncode != 0
    assert run_script("install-shortcut.ps1", "-Folder", str(tmp_path), "-Replace").returncode == 0
    assert run_script("install-shortcut.ps1", "-Folder", str(tmp_path), "-Remove").returncode == 0
    assert not (tmp_path / "SleepIQ.lnk").exists()


@pytest.mark.parametrize("name", ["launch.ps1", "launcher-tools.ps1", "install-shortcut.ps1"])
def test_launcher_scripts_parse_cleanly(name):
    out = ps(
        "$e=$null; [void][Management.Automation.Language.Parser]::ParseFile("
        f"'{(ROOT / 'scripts' / name).as_posix()}',[ref]$null,[ref]$e); "
        "if ($e) { $e | ForEach-Object { $_.Message }; exit 1 }"
    )
    assert out.returncode == 0, out.stdout
