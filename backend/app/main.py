import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.db import get_engine, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def initial_sync() -> None:
    """If there is no successful snapshot yet, sync once. Failures are recorded, never fatal."""
    from sqlmodel import Session

    from app.integrations.sources import SourceError, build_source
    from app.services.sync import current_run, run_sync

    with Session(get_engine()) as session:
        if current_run(session) is not None:
            return
        try:
            run = run_sync(session, build_source(get_settings()))
            log.info("startup sync: %s", run.status)
        except SourceError as exc:
            log.warning("startup sync skipped: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if get_settings().auto_sync_on_startup:
        initial_sync()
    yield


settings = get_settings()
app = FastAPI(
    title="Operations Intelligence API",
    description="Read-only ingestion, validation and reporting for operational data (demo, synthetic data).",
    version="0.1.0",
    lifespan=lifespan,
    # Interactive docs are disabled in production to keep the surface small.
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)
app.include_router(router)


@app.get("/health")
def health():
    """Unauthenticated liveness check for uptime monitoring."""
    return {"status": "ok"}
