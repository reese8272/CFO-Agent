"""Universal principle registry and year-versioned tax constants.

All year-versioned constants are sourced from IRS publications and stamped
with the tax year. The agent says "for <year>..." when citing any of these.
"""
from __future__ import annotations

TAX_YEAR = 2026

# --- 2026 IRS limits (Rev. Proc. 2025-32, Notice 2025-67, Rev. Proc. 2025-19) ---
ROTH_IRA_LIMIT_2026: int = 7_000
TRADITIONAL_IRA_LIMIT_2026: int = 7_000
HSA_LIMIT_SINGLE_2026: int = 4_300
HSA_LIMIT_FAMILY_2026: int = 8_550
K401_EMPLOYEE_LIMIT_2026: int = 23_500
SOLO_401K_TOTAL_LIMIT_2026: int = 69_000
MILEAGE_RATE_2026: float = 0.70          # IRS standard business mileage rate $/mile
SE_TAX_RATE: float = 0.1530             # 15.3% self-employment tax (SS + Medicare)
STANDARD_DEDUCTION_SINGLE_2026: int = 15_000
STANDARD_DEDUCTION_MFJ_2026: int = 30_000
HIGH_INTEREST_APR_THRESHOLD: float = 7.0  # debts above this APR beat expected market return


PRINCIPLES: dict[str, dict[str, str]] = {
    "assets_over_liabilities": {
        "name": "Assets over liabilities",
        "short": "Route every surplus dollar toward assets that pay you, not liabilities that drain you.",
        "cite": "Assets over liabilities: anything that puts money in your pocket without your active hours is an asset; anything that takes money out is a liability.",
    },
    "emergency_fund_first": {
        "name": "Emergency fund first",
        "short": "3–6 months of expenses in liquid cash eliminates forced bad decisions.",
        "cite": "Emergency fund first: without 3–6 months of expenses in liquid cash, any setback forces high-APR debt or panic-sold investments.",
    },
    "debt_avalanche": {
        "name": "Debt avalanche",
        "short": "Pay highest APR first — mathematically optimal, guaranteed return.",
        "cite": "Debt avalanche: each dollar against a high-APR balance returns that APR guaranteed — better than nearly any investment.",
    },
    "time_in_market": {
        "name": "Time-in-market",
        "short": "Compounding requires consistency; timing is luck.",
        "cite": "Time-in-market: missing the best 10 trading days per decade halves long-run returns — stay in.",
    },
    "tax_arbitrage": {
        "name": "Tax arbitrage",
        "short": "Pre-tax / Roth / taxable bucket selection by horizon and bracket.",
        "cite": "Tax arbitrage: Roth wins when current bracket < expected retirement bracket; pre-tax wins in reverse.",
    },
    "employer_match_capture": {
        "name": "Employer match capture",
        "short": "Never leave free money — a 100% match is a 100% instant return.",
        "cite": "Employer match capture: a 100% match on the first 6% is a 100% instant return — capture before anything else.",
    },
    "solo_401k_for_1099": {
        "name": "Solo 401k for 1099 income",
        "short": "Self-employment income qualifies for Solo 401k — far above the IRA limit.",
        "cite": f"Solo 401k for 1099 income: for {TAX_YEAR}, combined contributions can reach ${SOLO_401K_TOTAL_LIMIT_2026:,} — most gig workers don't know they qualify.",
    },
    "lifestyle_creep_avoidance": {
        "name": "Lifestyle creep avoidance",
        "short": "Direct raises to investment vehicles before they touch spend.",
        "cite": "Lifestyle creep avoidance: automate raises into Roth / brokerage before they hit checking — the wealth delta between same-comp earners is almost entirely this decision.",
    },
    "career_income_as_wealth_lever": {
        "name": "Career income as wealth lever",
        "short": "A $20k comp bump invested for 30 years beats most portfolio optimizations.",
        "cite": "Career income as wealth lever: comp delta invested early compounds further than nearly any allocation optimization on existing dollars.",
    },
    "real_estate_leverage": {
        "name": "Real estate leverage",
        "short": "20% down controls a 5x-leveraged asset — but only after Steps 1–4.",
        "cite": "Real estate leverage: your money controlling more money, with cash flow — Step 5, not Step 1, because it demands stability underneath.",
    },
    "business_income_compounding": {
        "name": "Business income compounding",
        "short": "Equity in a business scales independently of hours; W-2 doesn't.",
        "cite": "Business income compounding: separating earning from time-spent is the final step — requires every prior layer as foundation.",
    },
    "job_switch_comp_arbitrage": {
        "name": "Job-switch comp arbitrage",
        "short": "Average job-switch bump is 10–15% vs 3–5% internal raise — switch every 2–4 years.",
        "cite": "Job-switch comp arbitrage: the most reliable compounding move on the income side at the early-to-mid-career stage.",
    },
    "deduction_discipline_1099": {
        "name": "1099 deduction discipline",
        "short": "Every dollar deducted saves 25–35 cents in combined tax — track mileage, home office, equipment, education.",
        "cite": "1099 deduction discipline: self-employment income carries ~15.3% SE tax on top of ordinary income — every deduction is a 25–35% guaranteed return on the discipline of tracking.",
    },
    "side_income_hourly_truth": {
        "name": "Side-income hourly truth",
        "short": "Net hourly = (gross − stream expenses) / hours. Rank streams and cut the bottom when >30% below top.",
        "cite": "Side-income hourly truth: gross pay lies — compute net hourly across streams, rank them, and cut the bottom once it's more than 30% below the top.",
    },
    "quarterly_estimated_tax": {
        "name": "Quarterly estimated tax",
        "short": "1099 income owes quarterly — underpayment by >$1k triggers IRS penalty.",
        "cite": f"Quarterly estimated tax: for {TAX_YEAR}, 1099 income owes Apr 15 / Jun 15 / Sep 15 / Jan 15 — underpayment by more than $1,000 triggers a penalty plus interest.",
    },
    "comp_negotiation_anchor_high": {
        "name": "Comp negotiation: anchor high, ask in writing",
        "short": "Anchor at the top of your benchmark band. Get every offer in writing. Never accept on the call.",
        "cite": "Comp negotiation: anchor the conversation at the top of your benchmark band, get it in writing, never accept on the call.",
    },
}


def get_principle(key: str) -> str:
    """Return the cite string for a principle key. Raises KeyError on unknown key."""
    return PRINCIPLES[key]["cite"]


def get_all_keys() -> list[str]:
    return list(PRINCIPLES.keys())
