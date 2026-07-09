# Wealth-Building Framework & Named Principles

The agent reasons against **two parallel tracks** on every turn:

- **Allocation track** — what to do with the money you have. 6-step sequence below, computed by `vault/wealth_position.py`.
- **Income track** — how to make more money. 5-step sequence below, computed by `vault/income_position.py`.

The Synthesizer picks the single highest-leverage next move across both tracks. The user can ask "what's my position on the income track" or "what's my position on the allocation track" to drill into either.

> **Disclaimer**: This tool is for financial education and personal organization. It is not a licensed financial advisor. For tax strategy, real estate transactions, and investment decisions, consult a licensed professional.

---

## Allocation Track — The Wealth-Building Sequence

```
Step 1 — Stability          Emergency fund (3–6 months expenses) in cash/HYSA
Step 2 — Eliminate Drag     All high-interest debt (typically >7–8% APR) eliminated
Step 3 — Tax-Advantaged     Roth IRA maxed ($7k/year for 2026; verify annually)
                            Solo 401k for self-employed income (up to ~$69k/year; verify)
                            HSA if eligible (triple tax-advantaged)
Step 4 — Market Exposure    Consistent index-fund contribution (taxable brokerage)
Step 5 — Leverage           Real estate / rental property
Step 6 — Ownership          Business income that doesn't require your time
```

---

## Income Track — The Income-Generation Sequence

```
Step 1 — Net Hourly Truth      Compute true $/hr for every income stream
                               (gross − stream-specific expenses) / hours worked.
                               Rank streams by net hourly.

Step 2 — Cut the Bottom        Drop or scale-down the lowest-margin stream once
                               net hourly is more than 30% below the top stream.
                               Time freed reinvests into Step 3, 4, or 5.

Step 3 — Career Velocity       Comp benchmark for your role + metro.
                               Switch jobs every 2–4 years if comp delta beats
                               internal raise trajectory by >7%.

Step 4 — Deduction Discipline  Every 1099 deduction captured (mileage,
                               home office, equipment, education).
                               Quarterly estimated tax remitted to avoid penalty.

Step 5 — Negotiation Practice  Anchor high, ask in writing, every raise /
                               renewal / contract. Negotiation milestones
                               tracked and surfaced 30 days ahead.
```

---

## Named Principles the Coach Cites

The Coach node cites exactly one of these in one sentence per recommendation. The longer-form explanation is on demand only — the user asks "explain that more" and the entry below is expanded into a coaching paragraph.

### Assets over liabilities
Anything that puts money in your pocket without your active hours is an asset; anything that takes money out is a liability — the discipline is routing every surplus dollar toward the first category. A house you live in is a liability (mortgage, taxes, maintenance, opportunity cost on the down payment); a rental that cash-flows is an asset. A new car is a liability; a vehicle used in a deductible side business is partially an asset. This is the mental scaffold underneath the entire allocation track (Steps 5 and 6 explicitly) and the income track (career income and side businesses are assets that pay you). The Rich Dad framing, sharpened by Naval Ravikant's "specific knowledge + leverage + equity" and Codie Sanchez's "boring businesses that pay you while you sleep," is the lens every recommendation passes through.

### Emergency fund first
Eliminates forced bad decisions under stress. Without 3–6 months of expenses in liquid cash, any setback (job loss, medical, car) forces high-APR debt or panic-sold investments. Step 1 of the sequence for a reason.

### Debt avalanche
Pay highest APR first; mathematically optimal. Each dollar against a 22% APR balance returns 22% guaranteed — better than nearly any investment. Snowball (smallest balance first) trades dollars for motivation; only choose it if behavior is the actual bottleneck.

### Time-in-market
Compounding requires consistency; timing is luck. Statistically, missing the best 10 trading days per decade halves long-run returns. The win condition is "still contributing in 2046," not "bought the dip in 2026."

### Tax arbitrage
Pre-tax / Roth / taxable bucket selection by horizon and bracket. Roth wins when current bracket < expected retirement bracket; pre-tax wins in reverse. Taxable brokerage fills the gap when tax-advantaged room is exhausted or liquidity is needed before 59½.

### Employer match capture
Never leave free money. A 100% match on the first 6% is a 100% instant return — beats every other use of that dollar, including paying down a 22% APR credit card. Capture match before anything else.

### Solo 401k for 1099 income
Most gig workers don't know they qualify. Self-employment income (DoorDash, coaching, consulting) qualifies for a Solo 401k with combined employee + employer contributions far above the IRA limit. Year-versioned limits live in `agent/principles.py`.

### Lifestyle creep avoidance
Direct raises to investment vehicles, not spend. The wealth delta between two people earning the same comp is almost entirely explained by what each does with raises. Automate the raise into Roth / brokerage before it touches checking.

### Career income as wealth lever
Comp delta invested early beats most other moves. A $20k comp bump invested for 30 years at 7% becomes ~$152k — larger than nearly any optimization on existing dollars. The Strategist factors `career_position` target comp into long-horizon planning.

### Real estate leverage
Your money controlling more money, with cash flow. A 20% down payment controls a 5x-leveraged appreciating asset that ideally pays its own carrying cost. Step 5 — not Step 1 — because it demands a working emergency fund and stable cash flow underneath.

### Business income compounding
Separating earning from time-spent. W-2 and 1099 income scale linearly with hours; equity in a business scales independently of them. Step 6 — the final step — because it requires every prior layer (stability, no drag, tax shelter, market exposure, leverage) as foundation.

### Job-switch comp arbitrage
The average pay bump on a job switch runs ~10–15% (Pew, BLS) — meaningfully larger than the typical internal raise of ~3–5%. Switching every 2–4 years is the most reliable compounding move on the income side at the early-to-mid-career stage. The cost is real (interview load, learning curve, reset on tenure-based perks); the agent surfaces the math, not the decision.

### 1099 deduction discipline
Self-employment income carries roughly a 15.3% additional tax burden (Social Security + Medicare) on top of ordinary income tax. Every dollar correctly deducted saves ~$0.25–0.35 in combined tax — a 25–35% guaranteed return on the discipline of tracking. Mileage, home office, equipment, and education are the four buckets most underused by gig and coaching earners.

### Side-income hourly truth
Gross pay lies. The true comparison across income streams is **net hourly** — gross minus all stream-specific expenses (gas, food during shift, vehicle depreciation, opportunity cost) divided by hours worked. Rank streams by net hourly and cut the bottom once it's more than 30% below the top. Time is the constrained resource; protect it.

### Quarterly estimated tax
1099 income owes federal estimated tax quarterly (Apr 15 / Jun 15 / Sep 15 / Jan 15). Underpayment by more than $1,000 triggers an IRS penalty plus interest. The agent computes the suggested payment from year-to-date 1099 earnings × bracket × self-employment tax, citing the year-versioned constants in `agent/principles.py`. Disclaimer mandatory.

### Comp negotiation: anchor high, ask in writing
Compensation moves on three signals: market data (your benchmark), tenure (time in role), and demonstrable delivery (recent wins). Anchor the conversation at the top of your benchmark band, not the middle. Get every offer in writing before responding. Never accept on the call. The agent tracks negotiation milestones and surfaces them 30 days ahead so you have time to prep, not react.

### Arena principles (real estate / SaaS / investing)
The Coach can also cite the arena-specific principles registered in `docs/CONTRACTS.md` §4
(e.g. `house_hacking`, `cac_ltv`, `three_fund`). Their full cite text lives in
`agent/principles_real_estate.py`, `agent/principles_saas.py`, and `agent/principles_investing.py` —
that code is the source of truth; they are not duplicated here.

---

## Debt-Payoff vs Invest-Now Heuristic

Encoded heuristic, transparent and overridable:

- Debt with APR ≥ 7%: pay off before any non-match investing
- Debt with APR 4–7%: case-by-case based on user's risk tolerance and timeline; agent surfaces the math
- Debt with APR < 4%: minimum payments; redirect surplus to investing
- Employer 401k match is always first dollar regardless of debt (it's a 100% instant return)

User can override via a row in the `decisions` table.

---

## Year-Versioned Tax Constants

Year-versioned constants (Roth limit, Solo 401k limit, mileage rate, HSA limit) live in `agent/principles.py` and are stamped with the tax year. The agent says "for &lt;year&gt;..." every time it cites a number. Update annually.

---

## Arena-Specific Principle Libraries

When the user asks about real estate, SaaS / indie business, or investing specifically, the Coach pulls from arena-specific principle modules in addition to the universal principles above. These live in:

- `agent/principles_real_estate.py` — house hacking, BRRRR, cap rate, cash-on-cash, 1% rule, market analysis, REITs vs direct ownership, common mistakes
- `agent/principles_saas.py` — pricing, MRR/ARR, churn (gross + net dollar retention), CAC/LTV, distribution-first thinking, bootstrapping vs VC, when to leave W-2
- `agent/principles_investing.py` — three-fund portfolio (Bogleheads), target-date funds, tax-loss harvesting, asset allocation by age, rebalancing cadence

Content for each module is sourced from the research workflow in `docs/RESEARCH_PROMPT.md` (output → `docs/RESEARCH_NOTES.md` → ported into the module files during Issue 6 / Issue 8).

---

## Coach Voice

The Synthesizer system prompt encodes a specific tonal range, enforced through prompt engineering and verified by the eval harness in `tests/eval/`:

**Voice references**: Naval Ravikant (compounding leverage, specific knowledge), Codie Sanchez (boring businesses pay), Patrick McKenzie (negotiation as a fundamental skill), Bogleheads (boring index discipline), Morgan Housel (psychology over math).

**NOT**: hype, hustle-bro, get-rich-quick, magical thinking, condescending explainer, Suze-Orman-style finger-wagging.

**Always**: encouraging, real, doesn't sugarcoat, names the long game, stamps every recommendation against how it advances the 10-year vision.

---

## How the Agent Uses This

- **Strategist** picks the highest-leverage move on the **allocation track** given `wealth_position`.
- **Career** picks the highest-leverage move on the **income track** related to comp / switch / promotion / negotiation given `income_position` + `career_position` + `comp_benchmarks`.
- **Income-Optimizer** ranks streams by net hourly and surfaces cut-or-scale recommendations.
- **Tax-Optimizer** surfaces missed 1099 deductions and quarterly estimated tax suggestions.
- **Coach** cites exactly one of the named principles above (universal or arena-specific) in a single sentence.
- **Synthesizer** commits to ONE recommendation across whatever nodes fired, stamps it against the user's 10-year vision, and speaks in the Coach Voice above; refuses to enumerate options unless explicitly asked.
- **The agent's job is not to teach a class.** It cites the principle in one sentence per recommendation. The user can ask "explain that more" to get the longer lesson on demand.
