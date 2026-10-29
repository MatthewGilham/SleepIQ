"""Explicitly launched synthetic LAN probe; never imported by the dashboard."""

import os
import ssl
from pathlib import Path

import uvicorn

from app.transport.probe import create_probe


def configuration(token: str, certificates: Path) -> uvicorn.Config:
    return uvicorn.Config(
        create_probe(token),
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


def main() -> None:
    token = os.environ.pop("SLEEPIQ_PROBE_TOKEN")
    certificates = Path(os.environ.pop("SLEEPIQ_PROBE_CERTIFICATES"))
    config = configuration(token, certificates)
    # Validate the certificate/key pairing before binding. No plaintext fallback.
    config.load()
    if config.ssl is None:
        raise RuntimeError("TLS is required")
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
