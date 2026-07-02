"""Digest generator + cron tests — SMTP always mocked."""
from __future__ import annotations
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Digest content ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_digest_returns_markdown():
    """generate_digest returns a non-empty Markdown string with key sections."""
    from digest import generate_digest

    class FakeWealthLadder:
        def get(self, key, default=None):
            data = {
                "net_worth": Decimal("50000"),
                "total_assets": Decimal("60000"),
                "total_liabilities": Decimal("10000"),
                "allocation_ladder": [{"step": 1, "label": "Emergency Fund", "funded": True}],
                "open_gaps": [{"step": 2, "label": "Debt Elimination", "target": "Pay off card"}],
            }
            return data.get(key, default)

    class FakeIncomeLadder:
        def get(self, key, default=None):
            data = {
                "total_monthly_income": Decimal("4000"),
                "income_ladder": [{"step": 1, "label": "W-2 Income", "funded": True}],
                "open_gaps": [{"step": 2, "label": "Side Income"}],
            }
            return data.get(key, default)

    mock_wealth = FakeWealthLadder()
    mock_income = FakeIncomeLadder()

    mock_session = AsyncMock()
    mock_snap_result = MagicMock()
    mock_snap_result.scalars.return_value.all.return_value = []
    mock_pattern_result = MagicMock()
    mock_pattern_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(side_effect=[mock_snap_result, mock_pattern_result])

    with patch("digest.compute_wealth_position", AsyncMock(return_value=mock_wealth)), \
         patch("digest.compute_income_position", AsyncMock(return_value=mock_income)):
        body = await generate_digest(mock_session)

    assert "# Personal CFO Digest" in body
    assert "Net Worth" in body
    assert "Allocation Track" in body
    assert "Income Track" in body
    assert "Action Item" in body
    assert "not a licensed financial advisor" in body.lower() or "financial education" in body.lower()


@pytest.mark.asyncio
async def test_generate_digest_includes_week_delta():
    """generate_digest shows week-over-week net worth delta when two snapshots exist."""
    from digest import generate_digest

    class FakeWealthLadder:
        def get(self, key, default=None):
            data = {
                "net_worth": Decimal("52000"),
                "open_gaps": [],
                "allocation_ladder": [],
            }
            return data.get(key, default)

    class FakeIncomeLadder:
        def get(self, key, default=None):
            return {"open_gaps": [], "income_ladder": [], "total_monthly_income": Decimal("4000")}.get(key, default)

    class FakeSnap:
        def __init__(self, nw):
            self.net_worth = nw
            self.snapshot_at = datetime.now(timezone.utc)

    mock_session = AsyncMock()
    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = [
        FakeSnap(Decimal("52000")),
        FakeSnap(Decimal("50000")),
    ]
    pattern_result = MagicMock()
    pattern_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(side_effect=[snap_result, pattern_result])

    with patch("digest.compute_wealth_position", AsyncMock(return_value=FakeWealthLadder())), \
         patch("digest.compute_income_position", AsyncMock(return_value=FakeIncomeLadder())):
        body = await generate_digest(mock_session)

    assert "+$2,000" in body or "2,000" in body


# ── Email sending ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_and_send_digest_calls_smtp():
    """generate_and_send_digest calls smtplib.SMTP and send_message."""
    from digest import generate_and_send_digest

    mock_body = "# Digest\n\nTest content"

    mock_smtp_instance = MagicMock()
    mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("digest.generate_digest", AsyncMock(return_value=mock_body)), \
         patch("digest.get_sessionmaker", return_value=lambda: mock_ctx), \
         patch("smtplib.SMTP", mock_smtp_class):
        result = await generate_and_send_digest()

    assert result == mock_body
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_generate_and_send_digest_raises_on_smtp_error():
    """generate_and_send_digest re-raises SMTP errors."""
    from digest import generate_and_send_digest

    mock_smtp_class = MagicMock(side_effect=ConnectionRefusedError("SMTP down"))

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("digest.generate_digest", AsyncMock(return_value="# Digest")), \
         patch("digest.get_sessionmaker", return_value=lambda: mock_ctx), \
         patch("smtplib.SMTP", mock_smtp_class):
        with pytest.raises(ConnectionRefusedError):
            await generate_and_send_digest()


# ── Scheduler ─────────────────────────────────────────────────────────────────

def test_scheduler_has_weekly_digest_job():
    """APScheduler is configured with a weekly_digest job."""
    from worker.cron import get_scheduler, stop_scheduler

    try:
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        assert "weekly_digest" in job_ids
    finally:
        stop_scheduler()


def test_start_stop_scheduler():
    """Scheduler starts and stops without error."""
    from worker.cron import start_scheduler, stop_scheduler

    start_scheduler()
    stop_scheduler()  # should not raise
