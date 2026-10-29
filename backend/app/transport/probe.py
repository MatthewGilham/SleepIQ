"""HTTPS/auth ingress boundary. Health ingestion is off unless a handler is explicitly supplied."""

import asyncio
import hashlib
import hmac
import ipaddress
import re
import time
from collections import deque
from collections.abc import Callable
from threading import Lock

from fastapi import FastAPI, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.ingest.parse import UnsupportedExport


class IngressBoundary:
    def __init__(
        self,
        app: ASGIApp,
        token: str,
        subnet: str,
        limit: int = 60,
        body_limit: int = 4096,
        timeout: float = 5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.network = ipaddress.IPv4Network(subnet)
        private_ranges = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
        if (
            not any(
                self.network.subnet_of(ipaddress.IPv4Network(value)) for value in private_ranges
            )
            or self.network.prefixlen < 24
        ):
            raise ValueError("A narrowly scoped private IPv4 subnet is required")
        if min(limit, body_limit, timeout) <= 0:
            raise ValueError("Positive transport limits required")
        self.limit, self.body_limit, self.timeout, self.clock = limit, body_limit, timeout, clock
        self.requests: dict[str, deque[float]] = {}
        self.lock = Lock()
        self.rotate_token(token)

    def rotate_token(self, token: str) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", token) is None:
            raise ValueError("A generated 256-bit credential is required")
        digest = hashlib.sha256(b"Bearer " + token.encode("ascii")).digest()
        with self.lock:
            self.expected = digest

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def reject(status: int, detail: str) -> None:
            await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)

        if scope.get("scheme") != "https":
            await reject(426, "HTTPS required")
            return
        client = scope.get("client")
        try:
            address = ipaddress.IPv4Address(client[0] if client else "")
        except ipaddress.AddressValueError:
            await reject(403, "Forbidden")
            return
        if address not in self.network:
            await reject(403, "Forbidden")
            return
        headers = scope.get("headers", [])
        if any(key.lower() == b"origin" for key, _ in headers):
            await reject(403, "Forbidden")
            return
        now = self.clock()
        with self.lock:
            # The admitted /24 bounds the number of per-address queues to 256.
            requests = self.requests.setdefault(str(address), deque())
            while requests and requests[0] <= now - 60:
                requests.popleft()
            limited = len(requests) >= self.limit
            if not limited:
                requests.append(now)
        if limited:
            await reject(429, "Request limit exceeded")
            return
        if scope["path"] == "/health" and scope["method"] == "GET":
            await self.app(scope, receive, send)
            return
        credentials = [value for key, value in headers if key.lower() == b"authorization"]
        presented = credentials[0] if len(credentials) == 1 else b""
        with self.lock:
            authorized = hmac.compare_digest(hashlib.sha256(presented).digest(), self.expected)
        if not authorized:
            await reject(401, "Unauthorized")
            return
        if scope["method"] != "POST":
            await self.app(scope, receive, send)
            return
        content_types = [v for k, v in headers if k.lower() == b"content-type"]
        encodings = [v for k, v in headers if k.lower() == b"content-encoding"]
        if (
            len(content_types) != 1
            or content_types[0].split(b";")[0].strip().lower() != b"application/json"
            or any(v.lower() != b"identity" for v in encodings)
        ):
            await reject(415, "JSON required; compressed requests unsupported")
            return
        lengths = [v for k, v in headers if k.lower() == b"content-length"]
        if len(lengths) > 1:
            await reject(400, "Invalid content length")
            return
        if lengths:
            try:
                length = int(lengths[0])
            except ValueError:
                length = -1
            if length < 0 or length > self.body_limit:
                await reject(413 if length > self.body_limit else 400, "Request size rejected")
                return
        body = bytearray()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                message = await asyncio.wait_for(
                    receive(), timeout=max(0, deadline - time.monotonic())
                )
            except TimeoutError:
                await reject(408, "Request timeout")
                return
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.body_limit:
                await reject(413, "Request size rejected")
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if lengths and len(body) != int(lengths[0]):
            await reject(400, "Request size mismatch")
            return

        async def replay() -> Message:
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)


INGEST_BODY_LIMIT = 32 * 1024 * 1024
INGEST_TIMEOUT = 60.0


def create_probe(
    token: str,
    subnet: str = "192.168.1.0/24",
    *,
    limit: int = 60,
    body_limit: int = 4096,
    timeout: float = 5,
    clock: Callable[[], float] = time.monotonic,
    ingest: Callable[[bytes], dict[str, object]] | None = None,
) -> ASGIApp:
    """`ingest` (default None = disabled, 503) receives an authenticated, size-bounded JSON body."""
    if ingest is not None:
        body_limit, timeout = max(body_limit, INGEST_BODY_LIMIT), max(timeout, INGEST_TIMEOUT)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/transport-check")
    async def probe(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError, RecursionError):
            return JSONResponse({"detail": "Invalid JSON"}, status_code=400)
        if payload != {"probe": "sleepiq"}:
            return JSONResponse({"detail": "Synthetic probe payload required"}, status_code=422)
        return JSONResponse({"status": "transport_ok", "stored": False})

    @app.post("/api/ingest")
    async def receive(request: Request) -> JSONResponse:
        if ingest is None:
            return JSONResponse({"detail": "Health ingestion is not enabled"}, status_code=503)
        try:
            summary = await asyncio.to_thread(ingest, await request.body())
        except UnsupportedExport:
            return JSONResponse({"detail": "Unsupported export"}, status_code=422)
        except TimeoutError:
            return JSONResponse({"detail": "Importer busy; retry"}, status_code=503)
        except Exception:  # noqa: BLE001 - generic response on purpose; nothing was committed
            # Nothing was committed (atomic import). No payload or error text is returned/logged.
            return JSONResponse({"detail": "Import failed; retry"}, status_code=500)
        return JSONResponse(summary)

    boundary = IngressBoundary(app, token, subnet, limit, body_limit, timeout, clock)
    # Host check wraps all requests, including health and auth errors.
    return TrustedHostMiddleware(
        boundary, allowed_hosts=["sync.mgilham.online"], www_redirect=False
    )
