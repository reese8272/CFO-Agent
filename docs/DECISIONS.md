# Decisions Log

Architectural decisions that diverge from `docs/PRD.md` or `docs/SOT.md`, captured at the time the divergence is approved. Append-only. Newest at the top.

Format:
```
## YYYY-MM-DD — <title>
**Context**: what prompted the decision
**Decision**: what we're doing now
**Reasoning**: why this beats the prior plan
**Trade-offs**: what we give up
**Owner**: who approved
```

---

## 2026-05-24 — Pivot v1 from "Personal CFO" to "Personal CFO + Career Strategist"

**Context**: Owner question during the Issue 1 → Issue 2 transition: *"Does what I'm trying to accomplish here make sense? It's how can I make as much money as possible given my particular situation."* Original PRD focused heavily on **allocation** ("given a dollar, where does it go?") and lightly on **income generation** ("how do I make more dollars?"). For the stated goal, income generation is roughly half the equation and the owner's earning mix (W-2 + DoorDash + coaching) has unusually high upside on the income side.

**Decision**: Expand v1 scope to treat income generation as a first-class concern alongside allocation. Specifically:

*Schema additions:*
- `career_history` — past roles + comp + time-in-role (for switch-cadence analysis)
- `comp_benchmarks` — market data per role / metro (user-populated or agent-fetched on demand)
- `side_income_economics` — for each gig/1099 stream: gross, hours, expenses (gas, food, depreciation, opportunity cost), computed net hourly
- `tax_deductions_1099` — mileage log, home-office %, equipment, education, per tax year
- `negotiation_milestones` — upcoming reviews, contract renewals, raise-eligibility dates

*Agent additions:*
- **Career node** — comp benchmarks, switch timing, promotion-prep, raise-prep
- **Income-Optimizer node** — net hourly across streams, prune-or-scale recommendation
- **Tax-Optimizer node** — surfaces missed 1099 deductions, quarterly estimated tax. Could fold into Tracker; kept separate for single-responsibility.

*New named principles (in `docs/WEALTH_PRINCIPLES.md`):*
- Job-switch comp arbitrage (~10–15% delta documented on switch)
- 1099 deduction discipline (~$0.30 saved per $1 deducted at SE-tax rates)
- Side-income hourly truth (compare net hourly across streams; cut the lowest)
- Quarterly estimated tax (avoid IRS underpayment penalty)
- Comp negotiation: anchor high, ask in writing

*New backlog items:*
- Issues 2 and 4 expand to include the new schema entities and CRUD
- New Issue 8b: Career + Income-Optimizer + Tax-Optimizer nodes (may split during its Phase 1 CHECK if too big)

*North Star revision:* extended explicitly — *"Tell me where I am — across allocation AND income — and what my single highest-leverage next move is."*

**Reasoning**: The owner's stated goal has two compounding levers (income, allocation), not one. The prior scope only swung the second. Career switching at this stage of life typically beats any allocation optimization (Pew/BLS data on job-switch comp deltas runs ~10–15%), and 1099 income unlocks deductions and Solo 401(k) headroom that get left on the table without active tracking. Bolting income coaching on later would defer the highest-leverage analysis until after the easier-to-build allocation features ship.

**Trade-offs**:
- +1 issue (8b) and expansion of Issues 2 and 4 → estimate ~25–35% more work to first usable v1
- Larger agent surface area → more LLM tokens per turn, more eval coverage needed in `tests/eval/`
- External comp-benchmark API (Levels.fyi / BLS / Pew) deferred to a later issue; v1 takes user-entered benchmarks and lets the agent reason against them

---

## 2026-05-24 — Coach vision additions (small, additive, no re-pivot)

**Context**: After the morning pivot to "Personal CFO + Career Strategist," the owner clarified the felt experience they want: *"a coach… a financial guru that can help me become a millionaire… meets me at my particular spot and helps me get into real estate, SaaS, maximizing investments wisely."* Mapping that against the post-pivot scope showed five gaps: (1) asset-vs-liability framing not in principles, (2) net worth not the headline metric, (3) no arena-specific coaching libraries (real estate / SaaS / investing), (4) no long-horizon trajectory in synthesizer reasoning, (5) no coach voice specified for the Synthesizer prompt.

**Decision**: Layer these additions into the existing architecture without a third pivot. Specifically:

- **New named principle**: *"Assets over liabilities"* — Rich Dad / Naval / Codie Sanchez lens. Top-tier foundational principle added to `docs/WEALTH_PRINCIPLES.md`.
- **New schema entity**: `net_worth_snapshots` (assets, liabilities, computed net worth, breakdown JSONB, source). Folded into Issue 2.
- **New endpoint**: `GET /wealth/net_worth_trajectory` returning historical net worth vs target curve. Folded into Issue 5.
- **Arena-specific principle modules**: `agent/principles_real_estate.py`, `agent/principles_saas.py`, `agent/principles_investing.py`. Coach (Issue 8) loads from these in addition to `agent/principles.py` based on turn context. Content seeded from the research workflow in `docs/RESEARCH_PROMPT.md`.
- **Long-horizon trajectory requirement**: Synthesizer (Issue 8) stamps every recommendation with how it advances the 10-year vision. Tracker (Issue 10) computes net-worth-trajectory-vs-target and alerts when behind pace.
- **Coach voice**: Synthesizer system prompt encodes a specific tonal range — encouraging, real, doesn't sugarcoat, names the long game. References: Naval Ravikant, Codie Sanchez, Patrick McKenzie, Bogleheads, Morgan Housel. NOT: hype, hustle-bro, get-rich-quick, condescending explainer. Documented in `docs/WEALTH_PRINCIPLES.md`.
- **Research workflow**: `docs/RESEARCH_PROMPT.md` created; the owner runs it through an AI researcher (Claude with research / GPT deep research / Perplexity), drops output into `docs/RESEARCH_NOTES.md`, and the cleanest principles + year-versioned constants are ported into the relevant modules during Issues 6 and 8.

**Reasoning**: None of these requires architectural change. They're additive — one principle, one entity, one endpoint, three principle modules, two prompt-engineering requirements, one research artifact. No new issues; existing issues 2, 5, 8, 10, 12 scope-expand. Avoids a third pivot in a single day while still closing the gaps the owner named.

**Trade-offs**:
- Issues 2, 5, 8, 10, 12 grow modestly (each by one acceptance-criterion item)
- Arena modules increase the Coach's prompt token usage (more cached profile content) — fine given Anthropic prompt caching
- Coach voice as a prompt knob means tonal drift is possible; eval harness should add tone checks alongside content checks

**Owner**: reesepludwick@gmail.com (approved 2026-05-24)
