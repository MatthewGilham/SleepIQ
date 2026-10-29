"""Daily backup state and retry policy, active only while the app is running."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from threading import Lock

from app.db.backup import create_daily
from app.db.coordinator import write_guard


@dataclass(frozen=True)
class BackupState:
    status: str = "pending"
    last_success: str | None = None
    error: str | None = None


class BackupService:
    def __init__(self, data: Path, backups: Path, today: Callable[[], date] = date.today):
        self.data = data
        self.backups = backups
        self.today = today
        self.state = BackupState()
        self._run = Lock()

    def run_due(self) -> None:
        with self._run:
            day = self.today()
            if self.state.last_success == day.isoformat():
                return
            try:
                with write_guard(self.data):
                    create_daily(
                        self.data / "sleepiq.sqlite3", self.data / "raw", self.backups, day
                    )
            except (OSError, ValueError, TypeError, sqlite3.Error):
                self.state = BackupState("failed", self.state.last_success, "backup_failed")
            else:
                self.state = BackupState("ok", day.isoformat())
