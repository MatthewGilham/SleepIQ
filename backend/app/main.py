"""Local browser application; does not access private records."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.db.scheduler import BackupService


def create_app(
    frontend: Path | None = None,
    backup_service: BackupService | None = None,
    backup_interval: float = 3600,
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
