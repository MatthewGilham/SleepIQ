import asyncio
import secrets

import pytest
from app.transport.probe import IngressBoundary, create_probe
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.types import ASGIApp, Message

TOKEN = secrets.token_hex(32)  # ephemeral synthetic credential, never logged/committed
AUTH = {"Authorization": "Bearer " + TOKEN}


def client(
    app: ASGIApp | None = None,
    *,
    scheme: str = "https",
    host: str = "sync.mgilham.online",
    ip: str = "192.168.1.25",
) -> TestClient:
    return TestClient(app or create_probe(TOKEN), base_url=f"{scheme}://{host}", client=(ip, 12345))


def test_synthetic_probe_and_isolated_routes() -> None:
    with client() as session:
        assert session.get("/health").json() == {"status": "ok"}
        response = session.post("/transport-check", json={"probe": "sleepiq"}, headers=AUTH)
        assert response.json() == {"status": "transport_ok", "stored": False}
        for path in ["/", "/api/v1/status", "/docs", "/openapi.json"]:
            assert session.get(path, headers=AUTH).status_code == 404
        assert session.post("/api/ingest", json={}, headers=AUTH).status_code == 503


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "wrong"},
        [("Authorization", "Bearer " + TOKEN), ("Authorization", "wrong")],
    ],
)
def test_missing_wrong_duplicate_credentials_rejected(headers: object) -> None:
    with client() as session:
        response = session.post("/transport-check", json={"probe": "sleepiq"}, headers=headers)
        assert response.status_code == 401
        assert TOKEN not in response.text


@pytest.mark.parametrize(
    "options,headers,status",
    [
        ({"scheme": "http"}, AUTH, 426),
        ({"host": "attacker.invalid"}, AUTH, 400),
        ({"ip": "203.0.113.9"}, {**AUTH, "X-Forwarded-For": "192.168.1.25"}, 403),
        ({}, {**AUTH, "Origin": "https://attacker.invalid"}, 403),
    ],
)
def test_tls_host_source_and_origin_boundary(
    options: dict[str, str], headers: dict[str, str], status: int
) -> None:
    with client(**options) as session:
        assert (
            session.post("/transport-check", json={"probe": "sleepiq"}, headers=headers).status_code
            == status
        )


def test_size_type_encoding_and_malformed_body() -> None:
    with client() as session:
        assert (
            session.post("/transport-check", content=b"x" * 5000, headers=AUTH).status_code == 415
        )
        assert (
            session.post(
                "/transport-check",
                content=b"x" * 5000,
                headers={**AUTH, "Content-Type": "application/json"},
            ).status_code
            == 413
        )
        assert (
            session.post(
                "/transport-check",
                content=b"bad",
                headers={**AUTH, "Content-Type": "application/json"},
            ).status_code
            == 400
        )
        assert (
            session.post("/transport-check", json={"private-field": 123}, headers=AUTH).status_code
            == 422
        )
        assert (
            session.post(
                "/transport-check",
                content=b"gzip",
                headers={**AUTH, "Content-Type": "application/json", "Content-Encoding": "gzip"},
            ).status_code
            == 415
        )


def test_rate_limit_expires() -> None:
    now = [0.0]
    with client(create_probe(TOKEN, limit=2, clock=lambda: now[0])) as session:
        for _ in range(2):
            assert (
                session.post(
                    "/transport-check", json={"probe": "sleepiq"}, headers=AUTH
                ).status_code
                == 200
            )
        assert (
            session.post("/transport-check", json={"probe": "sleepiq"}, headers=AUTH).status_code
            == 429
        )
        now[0] = 61
        assert (
            session.post("/transport-check", json={"probe": "sleepiq"}, headers=AUTH).status_code
            == 200
        )


def test_weak_token_configuration_rejected() -> None:
    with pytest.raises(ValueError):
        create_probe("12345678")


def test_unauthorized_requests_are_also_limited() -> None:
    with client(create_probe(TOKEN, limit=1)) as session:
        assert session.post("/transport-check", json={}).status_code == 401
        assert session.post("/transport-check", json={}).status_code == 429


def test_deep_json_fails_safely() -> None:
    with client() as session:
        response = session.post(
            "/transport-check",
            content=b"[" * 1500,
            headers={**AUTH, "Content-Type": "application/json"},
        )
        assert response.status_code == 400


def test_rotation_revokes_previous_credential() -> None:
    downstream = FastAPI()

    @downstream.get("/check")
    def check() -> dict[str, bool]:
        return {"ok": True}

    boundary = IngressBoundary(downstream, TOKEN, "192.168.1.0/24")
    new_token = secrets.token_hex(32)
    boundary.rotate_token(new_token)
    with client(boundary) as session:
        assert session.get("/check", headers=AUTH).status_code == 401
        assert (
            session.get("/check", headers={"Authorization": "Bearer " + new_token}).status_code
            == 200
        )


def test_auth_rejected_before_body_is_read() -> None:
    async def run() -> None:
        sent: list[Message] = []

        async def receive() -> Message:
            pytest.fail("Unauthorized body was read")

        async def send(message: Message) -> None:
            sent.append(message)

        await create_probe(TOKEN)(
            {
                "type": "http",
                "scheme": "https",
                "method": "POST",
                "path": "/transport-check",
                "client": ("192.168.1.25", 12345),
                "headers": [(b"host", b"sync.mgilham.online")],
            },
            receive,
            send,
        )
        assert sent[0]["status"] == 401

    asyncio.run(run())


def test_chunked_limit_and_timeout() -> None:
    async def run(slow: bool) -> int:
        sent: list[Message] = []

        async def receive() -> Message:
            if slow:
                await asyncio.sleep(0.1)
            return {"type": "http.request", "body": b"x" * 20, "more_body": True}

        async def send(message: Message) -> None:
            sent.append(message)

        await create_probe(TOKEN, body_limit=30, timeout=0.01)(
            {
                "type": "http",
                "scheme": "https",
                "method": "POST",
                "path": "/transport-check",
                "client": ("192.168.1.25", 12345),
                "headers": [
                    (b"host", b"sync.mgilham.online"),
                    (b"authorization", ("Bearer " + TOKEN).encode()),
                    (b"content-type", b"application/json"),
                ],
            },
            receive,
            send,
        )
        return sent[0]["status"]

    assert asyncio.run(run(False)) == 413
    assert asyncio.run(run(True)) == 408
