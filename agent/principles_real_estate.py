"""Arena-specific principle library: real estate.

Loaded by Coach when turn_kind involves real estate questions.
"""
ARENA_PRINCIPLES: dict[str, str] = {
    "house_hacking": "House hacking: live in one unit, rent the others — your tenants pay your mortgage while you build equity and learn landlording at minimum risk.",
    "brrrr": "BRRRR (Buy, Rehab, Rent, Refinance, Repeat): recycle your down payment by refinancing after forced appreciation — but the math only works if ARV supports the new loan and cash flow survives the higher payment.",
    "one_percent_rule": "1% rule: monthly rent ≥ 1% of purchase price is a rough filter for positive cash flow — use it to screen markets, not close deals.",
    "cap_rate": "Cap rate = NOI / property value. A 6–8% cap rate in a stable market is the baseline; cap rate compression signals appreciation plays, not income plays.",
    "cash_on_cash": "Cash-on-cash return = annual pre-tax cash flow / total cash invested. Target ≥ 8% to beat the opportunity cost of liquid alternatives.",
    "market_analysis": "Buy in markets with positive population and job growth, rent-to-price ratio above 0.7%, and landlord-friendly regulation — the asset is only as good as its market.",
    "reits_vs_direct": "REITs offer liquidity and diversification but no leverage and no control; direct ownership offers leverage and control but illiquidity and active management. Match to your stage — REITs during Steps 1–4, direct when ready for Step 5.",
    "common_re_mistakes": "Common mistakes: overpaying in appreciation-only markets, underestimating vacancy and CapEx (budget 1–2% of property value/year for repairs), using ARV before the rehab is done, conflating cash flow with profit before vacancy.",
}
