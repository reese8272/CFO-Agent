# Wealth-Building Framework & Named Principles

The agent always reasons against this sequence. It must know which step the user is on and surface the next move accordingly. Encoded in `vault/wealth_position.py` and visible to the agent on every turn.

> **Disclaimer**: This tool is for financial education and personal organization. It is not a licensed financial advisor. For tax strategy, real estate transactions, and investment decisions, consult a licensed professional.

---

## The Wealth-Building Sequence

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

## Named Principles the Coach Cites

The Coach node cites exactly one of these in one sentence per recommendation. The longer-form explanation is on demand only — the user asks "explain that more" and the entry below is expanded into a coaching paragraph.

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

## How the Agent Uses This

- **Strategist** picks the highest-leverage move given current `wealth_position`.
- **Coach** cites exactly one of the named principles above in a single sentence.
- **Synthesizer** commits to one recommendation; refuses to enumerate options unless explicitly asked.
- **The agent's job is not to teach a class.** It cites the principle in one sentence per recommendation. The user can ask "explain that more" to get the longer lesson on demand.
