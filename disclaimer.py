"""Canonical disclaimer text used across every interface and the agent system prompt.

The disclaimer is mandatory on any response touching tax, legal, or investment
specifics. Structural enforcement (a test verifying the disclaimer appears
whenever required) lands in Issue 7 alongside the chat endpoint.
"""
import os

DISCLAIMER: str = (
    "This tool is for financial education and personal organization. "
    "It is not a licensed financial advisor. For tax strategy, real estate "
    "transactions, and investment decisions, consult a licensed professional."
)


def get_disclaimer() -> str:
    """Return the disclaimer, honoring the WEALTH_DISCLAIMER_TEXT override if set."""
    return os.environ.get("WEALTH_DISCLAIMER_TEXT") or DISCLAIMER
