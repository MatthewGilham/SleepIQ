import threading
from pathlib import Path

from app.transport.serve import run_backups

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


class FakeService:
    def __init__(self) -> None:
        self.calls = 0

    def run_due(self) -> None:
        self.calls += 1


def test_receiver_backup_loop_runs_at_start_repeats_and_stops_promptly() -> None:
    service = FakeService()
    stop = threading.Event()
    worker = threading.Thread(target=run_backups, args=(service, stop, 0.01), daemon=True)
    worker.start()
    while service.calls < 3:
        worker.join(0.01)
    stop.set()
    worker.join(2)
    assert not worker.is_alive() and service.calls >= 3


def test_backup_loop_runs_once_then_stops_when_already_stopped() -> None:
    service = FakeService()
    stop = threading.Event()
    stop.set()
    run_backups(service, stop, 3600)  # type: ignore[arg-type]
    assert service.calls == 1


def test_task_is_per_user_limited_hidden_and_runs_only_the_receiver() -> None:
    script = (SCRIPTS / "receiver-task.ps1").read_text(encoding="utf-8")
    assert "-RunLevel Limited" in script and "-LogonType Interactive" in script
    assert "-AtLogOn -User $user" in script
    assert "-WindowStyle Hidden" in script and "-Activate -EnableIngest" in script
    assert "start-probe.ps1" in script and "start.ps1" not in script.replace("start-probe.ps1", "")
    for forbidden in (
        "Bypass",
        "-RunLevel Highest",
        "SYSTEM",
        "New-Service",
        "Set-ExecutionPolicy",
    ):
        assert forbidden not in script
    assert "Unregister-ScheduledTask" in script  # one-command removal


def test_launcher_passes_backup_root_only_with_ingestion() -> None:
    script = (SCRIPTS / "start-probe.ps1").read_text(encoding="utf-8")
    inside = script.split("if ($EnableIngest) {", 1)[1].split("\n}", 1)[0]
    assert "SLEEPIQ_BACKUP_ROOT = $backupRoot" in inside
    assert script.count("SLEEPIQ_BACKUP_ROOT = $backupRoot") == 1
