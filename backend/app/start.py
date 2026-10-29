"""Launcher entry point; private data is explicitly opted in by start.ps1."""

import os
from pathlib import Path

from app.db.scheduler import BackupService
from app.main import create_app

data = os.environ.get("SLEEPIQ_DATA_ROOT")
backups = os.environ.get("SLEEPIQ_BACKUP_ROOT")
if bool(data) != bool(backups):
    raise RuntimeError("Both private data and backup folders must be configured")
service = BackupService(Path(data), Path(backups)) if data and backups else None
app = create_app(
    Path(__file__).resolve().parents[2] / "frontend/dist",
    service,
    chart_data=Path(data) if data else None,
)
