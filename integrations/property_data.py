"""Property value estimates via RentCast AVM.

Free tier: 50 calls/month. Requires RENTCAST_API_KEY in .env.
If the key is absent the caller receives None and the router returns 503.

Every response citing a RentCast estimate MUST include the disclaimer:
  "Property value is an automated estimate from RentCast, not a licensed appraisal.
   Consult a licensed appraiser or real estate professional for accurate valuation."

This is enforced in the router — not here — so the disclaimer travels with the
HTTP response rather than being buried in a library function.
"""
import logging
from dataclasses import dataclass
from decimal import Decimal

import requests

logger = logging.getLogger(__name__)

_RENTCAST_BASE = "https://api.rentcast.io/v1"
_AVM_DISCLAIMER = (
    "Property value is an automated estimate from RentCast, not a licensed appraisal. "
    "Consult a licensed appraiser or real estate professional for accurate valuation."
)


@dataclass
class PropertyEstimate:
    price: Decimal
    price_range_low: Decimal | None
    price_range_high: Decimal | None
    disclaimer: str = _AVM_DISCLAIMER


def fetch_property_estimate(address: str, api_key: str) -> PropertyEstimate | None:
    """Return a PropertyEstimate for the given address, or None on failure.

    Passes the address directly to the RentCast AVM endpoint. Logs a warning
    and returns None if the API call fails or the key is invalid.
    """
    try:
        resp = requests.get(
            f"{_RENTCAST_BASE}/avm/value",
            params={"address": address},
            headers={"X-Api-Key": api_key, "accept": "application/json"},
            timeout=15,
        )
        if resp.status_code == 401:
            logger.error("rentcast: invalid API key")
            return None
        if resp.status_code == 404:
            logger.warning("rentcast: no estimate found for address %r", address)
            return None
        resp.raise_for_status()
        data = resp.json()
        price = data.get("price")
        if price is None:
            logger.warning("rentcast: response missing 'price' field for %r", address)
            return None
        return PropertyEstimate(
            price=Decimal(str(price)),
            price_range_low=Decimal(str(data["priceRangeLow"])) if data.get("priceRangeLow") else None,
            price_range_high=Decimal(str(data["priceRangeHigh"])) if data.get("priceRangeHigh") else None,
        )
    except Exception:
        logger.warning("rentcast estimate failed for address %r", address)
        return None
