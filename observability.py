"""Request-scoped observability: a correlation id threaded through every log line.

A ``ContextVar`` holds the current request's id; ``RequestIdLogFilter`` injects it
into every log record, and the middleware in ``main.py`` sets it per request and
echoes it back in the ``X-Request-ID`` response header. This is what makes a
single request's failing path traceable across the app and the agent nodes
(the observability gap flagged in the 2026-07-03 assessment).
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

# Default "-" so records emitted outside any request (startup/shutdown) still format.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def new_request_id() -> str:
    """A short, unique-enough correlation id for one request."""
    return uuid.uuid4().hex[:16]


class RequestIdLogFilter(logging.Filter):
    """Inject the current request id into every log record as ``request_id``."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def init_error_tracking() -> None:
    """Initialize Sentry error tracking IF ``SENTRY_DSN`` is set (no-op otherwise).

    PII scrubbing is on (``send_default_pii=False``) — this is a finance app, so
    no request bodies, headers, or user data leave the box. Tracing is off
    (errors only). Missing DSN → inert; missing package → logged and skipped, so
    the app never fails to start over an optional observability dependency.
    """
    from config import get_settings

    settings = get_settings()
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        logging.getLogger(__name__).warning(
            "SENTRY_DSN is set but sentry-sdk is not installed; error tracking disabled"
        )
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        send_default_pii=False,   # never attach PII/request bodies (finance data)
        traces_sample_rate=0.0,   # error tracking only
    )
    logging.getLogger(__name__).info("sentry error tracking enabled (env=%s)", settings.env)
