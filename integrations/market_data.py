"""Stock and ETF price lookups via yfinance (primary) + Alpha Vantage (fallback).

Public market data is unencrypted — prices are fetched from public sources and
stored as plain Numeric in the holdings table. No sensitive data passes through
these functions.

Alpha Vantage fallback: free tier supports 25 requests/day. Set ALPHA_VANTAGE_KEY
in .env to enable. If absent, fallback is skipped and the function returns None.
"""
import asyncio
import logging
from decimal import Decimal

import requests
import yfinance as yf

from config import get_settings

logger = logging.getLogger(__name__)

_ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
# Reuse one pooled session for Alpha Vantage instead of a fresh connection per call.
_session = requests.Session()


async def fetch_price_async(ticker: str, timeout: float = 15.0) -> Decimal | None:
    """Off-load the blocking price fetch to a worker thread with a hard deadline.

    `fetch_price` is synchronous (yfinance + requests), so calling it directly on
    the event loop stalls every concurrent request. Running it via `to_thread`
    keeps the loop responsive; `wait_for` bounds a slow/hung upstream (yfinance
    exposes no timeout of its own).
    """
    try:
        return await asyncio.wait_for(asyncio.to_thread(fetch_price, ticker), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("price fetch timed out for %s after %ss", ticker, timeout)
        return None


def fetch_price(ticker: str) -> Decimal | None:
    """Return the latest price for a ticker, or None on failure.

    Tries yfinance first; falls back to Alpha Vantage if the result is None
    and ALPHA_VANTAGE_KEY is configured.
    """
    price = _fetch_yfinance(ticker)
    if price is not None:
        return price

    settings = get_settings()
    if settings.alpha_vantage_key:
        price = _fetch_alpha_vantage(ticker, settings.alpha_vantage_key)

    return price


def _fetch_yfinance(ticker: str) -> Decimal | None:
    try:
        info = yf.Ticker(ticker).fast_info
        raw = info.last_price
        if raw is None:
            return None
        return Decimal(str(raw))
    except Exception:
        logger.warning("yfinance price fetch failed for %s", ticker)
        return None


def _fetch_alpha_vantage(ticker: str, api_key: str) -> Decimal | None:
    try:
        # Alpha Vantage free tier requires the API key as a query parameter — no header option exists.
        # Never log `resp.url` or the params dict here; the key would appear in the log.
        resp = _session.get(
            _ALPHA_VANTAGE_URL,
            params={"function": "GLOBAL_QUOTE", "symbol": ticker, "apikey": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        price_str = data.get("Global Quote", {}).get("05. price")
        if not price_str:
            logger.warning("alpha vantage returned no price for %s", ticker)
            return None
        return Decimal(price_str)
    except Exception:
        logger.warning("alpha vantage price fetch failed for %s", ticker)
        return None
