import secrets
from datetime import date
from pathlib import Path

from app.ingest.service import make_handler
from app.transport.probe import create_probe
from app.transport.serve import configuration
from factories import new_store, nights_payload
from fastapi.testclient import TestClient

TOKEN = secrets.token_hex(32)
AUTH = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}


def session(app) -> TestClient:  # type: ignore[no-untyped-def]
    return TestClient(app, base_url="https://sync.mgilham.online", client=("192.168.1.25", 1))


def test_large_upload_needs_the_explicit_ingest_handler(scratch: Path) -> None:
    data, engine = new_store(scratch)
    engine.dispose()
    body = nights_payload(date(2025, 1, 1), 360)  # several MB, like a real batch
    assert len(body) > 500_000
    with session(create_probe(TOKEN)) as client:  # default: disabled, small body cap
        assert client.post("/api/ingest", content=body, headers=AUTH).status_code == 413
    with session(create_probe(TOKEN, ingest=make_handler(data))) as client:
        response = client.post("/api/ingest", content=body, headers=AUTH)
    assert response.status_code == 200 and response.json()["new"] > 1000


def test_server_configuration_accepts_a_handler_and_keeps_tls_only(scratch: Path) -> None:
    config = configuration(TOKEN, scratch, lambda _: {})
    assert config.ssl_certfile and config.proxy_headers is False and config.access_log is False


def test_launcher_enables_ingestion_only_with_its_explicit_switch() -> None:
    script = (Path(__file__).resolve().parents[3] / "scripts/start-probe.ps1").read_text()
    assert "[switch]$EnableIngest" in script
    inside = script.split("if ($EnableIngest) {", 1)[1].split("}", 1)[0]
    assert "SLEEPIQ_INGEST_DATA = $dataRoot" in inside
    assert script.count("SLEEPIQ_INGEST_DATA = $dataRoot") == 1
