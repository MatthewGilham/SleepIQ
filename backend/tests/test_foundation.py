from pathlib import Path

from app.main import create_app
from fastapi.testclient import TestClient


def test_health_contains_no_private_details() -> None:
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        assert client.post("/api/ingest", json={}).status_code == 404


def test_untrusted_host_is_rejected() -> None:
    with TestClient(create_app(), base_url="http://attacker.invalid") as client:
        assert client.get("/api/v1/health").status_code == 400


def test_frontend_and_api_share_origin() -> None:
    fixture = Path(__file__).resolve().parents[2] / "test_fixtures/web"
    with TestClient(create_app(fixture), base_url="http://127.0.0.1") as client:
        assert "Foundation" in client.get("/").text
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        assert client.get("/../.env").status_code == 404
