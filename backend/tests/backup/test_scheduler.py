import time
from datetime import date
from pathlib import Path

import pytest
from app.db import scheduler
from app.db.coordinator import write_guard
from app.db.initialize import initialize
from app.db.scheduler import BackupService
from app.main import create_app
from fastapi.testclient import TestClient


def service_for(scratch: Path, today: date) -> BackupService:
    data = scratch / "data"
    data.mkdir()
    initialize(data)
    backups = scratch / "backups"
    backups.mkdir()
    return BackupService(data, backups, lambda: today)


def test_same_day_no_duplicate_and_next_launch_catches_up(scratch: Path) -> None:
    service = service_for(scratch, date(2026, 10, 1))
    service.run_due()
    service.run_due()
    assert service.state.status == "ok"
    restarted = BackupService(service.data, service.backups, lambda: date(2026, 10, 29))
    restarted.run_due()
    assert restarted.state.last_success == "2026-10-29"
    assert sorted(p.name for p in service.backups.iterdir()) == ["2026-10-01", "2026-10-29"]


def test_failure_visible_and_retry_succeeds(scratch: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = service_for(scratch, date(2026, 10, 29))
    real_create = scheduler.create_daily

    def fail(*args: object) -> Path:
        raise OSError("Synthetic private-marker must not reach browser")

    monkeypatch.setattr(scheduler, "create_daily", fail)
    with TestClient(create_app(backup_service=service), base_url="http://127.0.0.1") as client:
        assert client.get("/api/v1/health").status_code == 200
        status = client.get("/api/v1/status")
        assert status.json()["backup"] == {
            "status": "failed",
            "last_success": None,
            "error": "backup_failed",
        }
        assert "private-marker" not in status.text
        monkeypatch.setattr(scheduler, "create_daily", real_create)
        service.run_due()
        assert service.state.status == "ok"


def test_running_app_backs_up_new_date_and_stops_polling(scratch: Path) -> None:
    service = service_for(scratch, date(2026, 10, 28))
    current = [date(2026, 10, 28)]
    service.today = lambda: current[0]
    with TestClient(
        create_app(backup_service=service, backup_interval=0.02), base_url="http://127.0.0.1"
    ) as client:
        assert service.state.last_success == "2026-10-28"
        current[0] = date(2026, 10, 29)
        deadline = time.monotonic() + 5
        while service.state.last_success != "2026-10-29":
            assert time.monotonic() < deadline
            time.sleep(0.01)
        assert client.get("/api/v1/status").json()["backup"]["status"] == "ok"
    current[0] = date(2026, 10, 30)
    time.sleep(0.05)
    assert service.state.last_success == "2026-10-29"


def test_held_writer_lock_is_not_bypassed(scratch: Path) -> None:
    with write_guard(scratch), pytest.raises(TimeoutError), write_guard(scratch, timeout=0.01):
        pytest.fail("Conflicting lock acquired")
