"""Weekly digest generator and email sender.

Pulls current vault state, builds a Markdown summary, and sends it via SMTP.
Called by the weekly cron job and the /digest/run-now endpoint.
"""
from __future__ import annotations
import asyncio
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db import get_sessionmaker
from disclaimer import get_disclaimer
from vault.wealth_position import compute_wealth_position
from vault.income_position import compute_income_position

logger = logging.getLogger(__name__)


async def generate_digest(session: AsyncSession) -> str:
    """Build the full Markdown digest from current vault state."""
    from vault.models import NetWorthSnapshot
    from memory.models import Pattern

    # ── wealth + income position ──────────────────────────────────────────────
    wealth = await compute_wealth_position(session, "owner")
    income = await compute_income_position(session, "owner")

    current_nw = wealth.get("net_worth", None)

    # ── last two net-worth snapshots for week-over-week delta ─────────────────
    result = await session.execute(
        select(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.snapshot_at.desc())
        .limit(2)
    )
    snaps = list(result.scalars().all())
    nw_delta: str | None = None
    if snaps:
        latest_nw = snaps[0].net_worth
        prior_nw = snaps[1].net_worth if len(snaps) >= 2 else None
        if latest_nw is not None and prior_nw is not None:
            delta = latest_nw - prior_nw
            sign = "+" if delta >= 0 else ""
            nw_delta = f"{sign}${delta:,.0f}"

    # ── new alerts in the last 7 days ─────────────────────────────────────────
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = await session.execute(
        select(Pattern)
        .where(Pattern.detected_at >= cutoff)
        .order_by(Pattern.detected_at.desc())
        .limit(5)
    )
    recent_alerts = list(result.scalars().all())

    # ── allocation + income ladder open gaps ──────────────────────────────────
    w_open = wealth.get("open_gaps", [])
    i_open = income.get("open_gaps", [])

    w_step = w_open[0]["step"] if w_open else 6
    w_name = w_open[0]["label"] if w_open else "All steps funded"
    w_next = w_open[0].get("target", "Continue investing") if w_open else "Scale passive income"

    i_step = i_open[0]["step"] if i_open else 5
    i_name = i_open[0]["label"] if i_open else "All income steps funded"
    i_next = f"Address: {i_open[0]['label']}" if i_open else "Scale passive income sources"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── build markdown ────────────────────────────────────────────────────────
    lines: list[str] = [
        f"# Personal CFO Digest — {today}",
        "",
        "## Net Worth",
    ]
    if current_nw is not None:
        nw_str = f"${current_nw:,.0f}"
        delta_str = f" | Week-over-week: {nw_delta}" if nw_delta else ""
        lines.append(f"**Current**: {nw_str}{delta_str}")
    else:
        lines.append("No net worth snapshot available yet. Add one in the vault.")

    lines += [
        "",
        "## Allocation Track",
        f"**Step {w_step}/6** — {w_name}",
        f"Next move: {w_next}",
        "",
        "## Income Track",
        f"**Step {i_step}/5** — {i_name}",
        f"Next move: {i_next}",
        "",
        "## Recent Alerts",
    ]

    if recent_alerts:
        for a in recent_alerts:
            sev = a.severity.upper()
            lines.append(f"- [{sev}] {a.summary}")
    else:
        lines.append("No new alerts this week.")

    lines += [
        "",
        "## One Action Item",
        f"→ {w_next if w_step < 6 else i_next}",
        "",
        "---",
        f"*{get_disclaimer()}*",
    ]

    return "\n".join(lines)


def _send_email_sync(subject: str, body: str, settings) -> None:
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password, settings.smtp_from]):
        raise RuntimeError("SMTP is not configured — set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = settings.digest_recipient
    msg.attach(MIMEText(body, "plain"))

    # timeout so a wedged/blackholed SMTP host can't hang the worker thread (and
    # the awaiting /digest/run-now request) forever.
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


async def generate_and_send_digest() -> str:
    """Build the digest and send it. Returns the Markdown body."""
    settings = get_settings()
    async with get_sessionmaker()() as session:
        body = await generate_digest(session)

    subject = f"Personal CFO Digest — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    try:
        await asyncio.to_thread(_send_email_sync, subject, body, settings)
        logger.info("digest sent to %s", settings.digest_recipient)
    except Exception as exc:
        logger.error("digest email failed: %s", exc)
        raise

    return body
