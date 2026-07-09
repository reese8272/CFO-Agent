"""Shared limit/offset pagination params for list endpoints.

Caps unbounded list queries (assessment Phase 4b). Defaults are generous so
the HTMX UI keeps rendering full lists at personal-use scale; cursor-based
pagination is deferred to Road B (docs/WEB_STANDARDS.md §4, DECISIONS 2026-07-09).
"""
from typing import Annotated

from fastapi import Query

DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 1000

LimitParam = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Max rows returned")]
OffsetParam = Annotated[int, Query(ge=0, description="Rows to skip")]
