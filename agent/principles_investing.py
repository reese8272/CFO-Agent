"""Arena-specific principle library: investing.

Loaded by Coach when turn_kind involves investing or portfolio questions.
"""
ARENA_PRINCIPLES: dict[str, str] = {
    "three_fund": "Three-fund portfolio (Bogleheads): total US market + total international + total bond market in a single tax-advantaged account. Low cost, diversified, rebalanced annually — beats 90% of active managers over 20 years.",
    "target_date_funds": "Target-date funds are the correct default for most 401k participants — automatic glide path, one decision, low cost. Override only if you have strong conviction on allocation and the discipline to rebalance manually.",
    "tax_loss_harvesting": "Tax-loss harvesting: sell losing positions to realize the tax deduction, immediately repurchase a similar-but-not-identical fund to maintain exposure. Only valuable in taxable accounts; watch the wash-sale rule (30-day window).",
    "asset_allocation": "Age-based rule of thumb: hold (100 − age)% in equities. More precise: match stock allocation to your investment horizon and risk tolerance, not just age — a 35-year-old with 30-year money can hold 90%+ equities.",
    "rebalancing": "Rebalance when any asset class drifts more than 5% from target, or annually at minimum. Threshold rebalancing (drift-based) beats calendar rebalancing slightly but calendar is fine for most.",
    "cost_matters": "A 1% expense ratio drag over 30 years destroys ~25% of terminal value vs a 0.03% index fund. Minimize costs above all else in tax-advantaged accounts.",
    "bonds_purpose": "Bonds dampen volatility and provide dry powder during equity drawdowns — not primarily a return source at current yields. Size your bond allocation to match your ability to stay invested during a 40–50% equity drawdown.",
}
