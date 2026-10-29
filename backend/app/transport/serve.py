"""Explicitly launched synthetic LAN probe; never imported by the dashboard."""

import os
import ssl
import threading
from collections.abc import Callable
from pathlib import Path

import uvicorn

from app.db.scheduler import BackupService
from app.ingest.service import make_handler
from app.transport.probe import create_probe


def configuration(
    token: str, certificates: Path, ingest: Callable[[bytes], dict[str, object]] | None = None
) -> uvicorn.Config:
    return uvicorn.Config(
        create_probe(token, ingest=ingest),
        host="192.168.1.190",
        port=8443,
        proxy_headers=False,
        access_log=False,
        server_header=False,
        log_level="warning",
        ws="none",
        limit_concurrency=16,
        timeout_keep_alive=5,
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
        ssl_certfile=str(certificates / "sync.mgilham.online.crt"),
        ssl_keyfile=str(certificates / "sync.mgilham.online.key"),
    )


def run_backups(service: BackupService, stop: threading.Event, interval: float = 3600) -> None:
    """Daily-backup check at start and hourly. A failed attempt is retried on the next tick."""
    while True:
        service.run_due()
        if stop.wait(interval):
            return


def main() -> None:
    token = os.environ.pop("SLEEPIQ_PROBE_TOKEN")
    certificates = Path(os.environ.pop("SLEEPIQ_PROBE_CERTIFICATES"))
    # Health ingestion stays disabled unless the owner explicitly names a private data folder.
    data = os.environ.pop("SLEEPIQ_INGEST_DATA", None)
    config = configuration(token, certificates, make_handler(Path(data)) if data else None)
    # Validate the certificate/key pairing before binding. No plaintext fallback.
    config.load()
    if config.ssl is None:
        raise RuntimeError("TLS is required")
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
    backups = os.environ.pop("SLEEPIQ_BACKUP_ROOT", None)
    stop = threading.Event()
    if data and backups:
        # An always-on receiver also protects the data it writes (same writer gate as imports).
        threading.Thread(
            target=run_backups, args=(BackupService(Path(data), Path(backups)), stop), daemon=True
        ).start()
    try:
        uvicorn.Server(config).run()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
