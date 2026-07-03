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
