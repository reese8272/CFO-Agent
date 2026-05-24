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

**Owner**: reesepludwick@gmail.com (approved 2026-05-24)
