"""Canonical disclaimer text used across every interface and the agent system prompt.

The disclaimer is mandatory on any response touching tax, legal, or investment
specifics. Enforcement is layered: the LLM sets requires_disclaimer, specialist
proposals can force it, and text_requires_disclaimer() is the deterministic
keyword backstop for when every LLM flag misses (observed 2026-07-09: a
debt-vs-invest answer named the Roth IRA with no flag set).
"""
import re

from config import get_settings

DISCLAIMER: str = (
    "This tool is for financial education and personal organization. "
    "It is not a licensed financial advisor. For tax strategy, real estate "
    "transactions, and investment decisions, consult a licensed professional."
)


# Terms that make a response "touch tax, legal, or investment specifics".
# Over-matching is safe (an extra disclaimer is compliant); under-matching is not.
_SENSITIVE_TERMS = re.compile(
    r"\b("
    r"tax(es|able|-free)?|deduct\w*|irs|"
    r"roth|ira|401\(?k\)?|hsa|brokerage|invest\w*|index fund|etf|stocks?|bonds?|"
    r"capital gains?|dividends?|compound\w*|"
    r"real estate|property|mortgage|refinanc\w*|escrow|"
    r"llc|legal|attorney|estate plan\w*"
    r")\b",
    re.IGNORECASE,
)


def text_requires_disclaimer(text: str) -> bool:
    """Deterministic backstop: does this response text touch tax/legal/investment?"""
    return bool(_SENSITIVE_TERMS.search(text))


def get_disclaimer() -> str:
    """Return the disclaimer, honoring the `wealth_disclaimer_text` setting override.

    Reads through the typed Settings (single source of truth) rather than
    `os.environ` — pydantic-settings loads `.env` into Settings without exporting
    to the process env, so an `os.environ` read silently missed a `.env` override.
    """
    return get_settings().wealth_disclaimer_text or DISCLAIMER
