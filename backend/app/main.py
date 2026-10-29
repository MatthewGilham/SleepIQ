"""Local browser application; does not access private records."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, Response

from app.ai.api import router as ai_router
from app.ai.config import AiConfig
from app.ai.provider import Provider
from app.analytics.api import router
from app.analytics.export import router as export_router
from app.db.engine import open_engine
from app.db.scheduler import BackupService


def create_app(
    frontend: Path | None = None,
    backup_service: BackupService | None = None,
    backup_interval: float = 3600,
    chart_data: Path | None = None,
    chart_synthetic: bool = False,
    ai_config: AiConfig | None = None,
    ai_provider: Provider | None = None,
) -> FastAPI:
    if backup_interval <= 0:
        raise ValueError("Backup interval must be positive")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        stopping = asyncio.Event()

        async def periodic() -> None:
            while not stopping.is_set():
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=backup_interval)
                except TimeoutError:
                    if backup_service is not None:
                        await asyncio.to_thread(backup_service.run_due)

        task = None
        if backup_service is not None:
            await asyncio.to_thread(backup_service.run_due)
            task = asyncio.create_task(periodic())
        try:
            yield
        finally:
            stopping.set()
            if task is not None:
                await task

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def chart_boundary(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        protected = request.url.path.startswith(
            (
                "/api/v1/analytics",
                "/api/v1/presets",
                "/api/v1/metrics",
                "/api/v1/dashboard",
                "/api/v1/analysis",
            )
        )
        if protected:
            if not request.client or request.client.host not in ("127.0.0.1", "::1"):
                return JSONResponse({"detail": "Local access required"}, status_code=403)
            origin = request.headers.get("origin")
            expected = str(request.base_url).rstrip("/")
            if origin and origin != expected:
                return JSONResponse({"detail": "Origin rejected"}, status_code=403)
            if request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
                return JSONResponse({"detail": "Origin rejected"}, status_code=403)
            if request.method in ("POST", "PUT", "DELETE"):
                if origin != expected or request.headers.get("x-sleepiq-request") != "charts":
                    return JSONResponse(
                        {"detail": "Same-origin chart request required"}, status_code=403
                    )
                size = 0
                chunks = []
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 16384:
                        return JSONResponse({"detail": "Request too large"}, status_code=413)
                    chunks.append(chunk)
                request._body = b"".join(chunks)
            if chart_data is None:
                return JSONResponse({"detail": "Chart store not configured"}, status_code=503)
        response = await call_next(request)
        if protected:
            response.headers["Cache-Control"] = "no-store"
        return response

    if chart_data is not None:
        database = chart_data / "sleepiq.sqlite3"
        if not database.is_file():
            raise ValueError("Initialized chart store required")
        engine = open_engine(database)
        app.include_router(router(engine, chart_data, chart_synthetic))
        app.include_router(export_router(engine))
        app.include_router(ai_router(engine, chart_data, ai_config or AiConfig(), ai_provider))

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/status")
    def status() -> dict[str, object]:
        state: dict[str, object] = {"status": "not_configured", "last_success": None, "error": None}
        if backup_service is not None:
            state = asdict(backup_service.state)
        return {"backup": state}

    if frontend is not None and frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app(Path(__file__).resolve().parents[2] / "frontend/dist")
