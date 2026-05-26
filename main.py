"""FastAPI entrypoint.

Wires startup/shutdown of external clients, exposes /health, and serves as
the mount point for routers added in later issues.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

import auth
import clients
import db
from config import get_settings
from disclaimer import get_disclaimer
from routers import vault as vault_router
from routers.holdings import router as holdings_router, side_event_router
from routers.imports import router as imports_router
from routers.chat import router as chat_router
from routers.wealth import router as wealth_router
from routers.memory import router as memory_router
from routers.scenarios import router as scenarios_router
from routers.digest import router as digest_router
from worker.cron import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _configure_logging()
    settings = get_settings()
    logger.info("starting personal-cfo (env=%s)", settings.env)
    db.get_engine()
    clients.get_redis()
    start_scheduler()
    yield
    stop_scheduler()
    await clients.close_redis()
    await db.dispose_engine()
    logger.info("shutdown complete")


app = FastAPI(
    title="Personal CFO",
    description=get_disclaimer(),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(vault_router.router)
app.include_router(holdings_router)
app.include_router(side_event_router)
app.include_router(imports_router)
app.include_router(wealth_router)
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(scenarios_router)
app.include_router(digest_router)

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/health")
async def health() -> JSONResponse:
    postgres_ok = await db.ping()
    redis_ok = await clients.ping_redis()
    payload = {
        "status": "ok" if (postgres_ok and redis_ok) else "degraded",
        "postgres": "ok" if postgres_ok else "down",
        "redis": "ok" if redis_ok else "down",
    }
    status_code = 200 if (postgres_ok and redis_ok) else 503
    return JSONResponse(content=payload, status_code=status_code)
