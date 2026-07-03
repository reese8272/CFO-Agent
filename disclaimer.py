"""Canonical disclaimer text used across every interface and the agent system prompt.

The disclaimer is mandatory on any response touching tax, legal, or investment
specifics. Structural enforcement (a test verifying the disclaimer appears
whenever required) lands in Issue 7 alongside the chat endpoint.
"""
from config import get_settings

DISCLAIMER: str = (
    "This tool is for financial education and personal organization. "
    "It is not a licensed financial advisor. For tax strategy, real estate "
    "transactions, and investment decisions, consult a licensed professional."
)


def get_disclaimer() -> str:
    """Return the disclaimer, honoring the `wealth_disclaimer_text` setting override.

    Reads through the typed Settings (single source of truth) rather than
    `os.environ` — pydantic-settings loads `.env` into Settings without exporting
    to the process env, so an `os.environ` read silently missed a `.env` override.
    """
    return get_settings().wealth_disclaimer_text or DISCLAIMER
