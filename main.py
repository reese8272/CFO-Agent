"""FastAPI entrypoint.

Wires startup/shutdown of external clients, exposes /health, and serves as
the mount point for routers added in later issues.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from pathlib import Path
from slowapi.errors import RateLimitExceeded

import auth
import clients
import db
from config import get_settings
from disclaimer import get_disclaimer
from observability import RequestIdLogFilter, new_request_id, request_id_var
from rate_limit import limiter
from routers import vault as vault_router
from routers.holdings import router as holdings_router, side_event_router
from routers.imports import router as imports_router
from routers.chat import router as chat_router
from routers.wealth import router as wealth_router
from routers.memory import router as memory_router
from routers.scenarios import router as scenarios_router
from routers.digest import router as digest_router
from routers.intake import router as intake_router
from worker.cron import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Structured logging with a per-request correlation id on every line."""
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s")
    )
    handler.addFilter(RequestIdLogFilter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]


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


_prod = get_settings().env == "production"
app = FastAPI(
    title="Personal CFO",
    description=get_disclaimer(),
    version="0.1.0",
    lifespan=lifespan,
    # Don't expose interactive API docs / schema in production.
    docs_url=None if _prod else "/docs",
    redoc_url=None if _prod else "/redoc",
    openapi_url=None if _prod else "/openapi.json",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.limiter = limiter


@app.middleware("http")
async def request_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Assign/propagate a correlation id per request; echo it in X-Request-ID.

    Accepts an inbound X-Request-ID (e.g. from an upstream proxy) or mints one,
    binds it to the logging ContextVar for the duration, and returns it so a
    client/operator can correlate a response with its server-side log lines.
    """
    rid = request.headers.get("x-request-id") or new_request_id()
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = rid
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Defense-in-depth response headers on every response.

    HSTS is only sent in production, where the public origin is HTTPS (TLS
    terminates at Cloudflare); sending it over plain-HTTP local dev would wrongly
    pin the browser. No CSP yet — the HTMX pages use inline handlers, so a strict
    policy is a separate effort (tracked in docs/PRODUCTION_ROADMAP.md).
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if _prod:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)

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
app.include_router(intake_router)

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/static/login.html")


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
