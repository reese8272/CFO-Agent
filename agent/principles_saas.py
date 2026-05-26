"""Arena-specific principle library: SaaS / indie business.

Loaded by Coach when turn_kind involves SaaS or business-building questions.
"""
ARENA_PRINCIPLES: dict[str, str] = {
    "mrr_arr": "MRR is your pulse; ARR is your valuation anchor. SaaS businesses trade at 5–15x ARR depending on growth rate and NRR — know your multiple before pricing a round or an exit.",
    "churn": "Gross churn (revenue lost from cancellations) is the floor; net dollar retention (NRR) is the ceiling. NRR > 100% means expansion revenue outpaces churn — the compounding business. Target NRR ≥ 110%.",
    "cac_ltv": "LTV:CAC ≥ 3:1 is the baseline for healthy unit economics; < 1:1 means you're buying customers at a loss. Payback period < 12 months is the cash-flow corollary.",
    "distribution_first": "Distribution first, product second — most indie SaaS businesses die from lack of distribution, not lack of features. Build your audience or your SEO moat before you build your next feature.",
    "pricing": "Raise prices. Most early-stage SaaS products are underpriced by 2–5x. Value-based pricing (charge for the outcome, not the input) separates sustainable businesses from churn machines.",
    "bootstrapping_vs_vc": "VC optimizes for a 100x outcome on a 10-year timeline — it's a specific game. Bootstrapping optimizes for a profitable business you own — a different game. Choose your game first; most solo founders win by bootstrapping.",
    "when_to_leave_w2": "Leave your W-2 when: (1) the business replaces your salary at 1.5x, (2) you have 6 months personal runway, and (3) the bottleneck is your time, not capital or distribution.",
}
