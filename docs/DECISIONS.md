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

## 2026-05-25 — Issue 4 vault CRUD: router factory, computed-field scope, side_income_event form deferral

**Context**: Issue 4 builds CRUD for 17 structurally-identical encrypted vault entities plus the ergonomic HTMX entry UI. Three implementation choices needed settling before the build.

**Decision**:
1. **Typed router factory over per-entity routers.** Generic async CRUD in `vault/crud.py` parameterized by model + schemas; a `make_crud_router(EntitySpec)` factory in `routers/vault.py` emits a five-verb resource per entity, all behind `get_current_user`. The factory is the single place mutations happen, so auth + audit + encryption can't be forgotten on a new entity. Pydantic schemas are still hand-written per entity (`vault/schemas.py`) — the API boundary is the validation/security surface — while the PATCH schema is generated all-optional from the create schema.
2. **Audit in the factory.** Every create/update/delete writes an append-only `audit_log` row; before/after snapshots are JSON-safe dicts stored through the existing `EncryptedJSON` column, so the snapshots are themselves Fernet-encrypted at rest (asserted in `tests/test_vault.py`).
3. **Computed fields: derive trivial arithmetic on write, defer the rest.** `equity_estimate`, `net_margin`, `net`, `net_hourly`, `net_worth` are computed server-side via `compute_*` callbacks and excluded from the create/update schemas (response-only). Fields needing rolling windows or year-versioned tax constants — `income_streams.rolling_4wk_avg`, `retirement_accounts.ytd_contribution_limit_remaining`, `goals.current_amount` — stay nullable for their owning issues (5 / 8) to populate.
4. **side_income_event form deferred to Issue 4b.** Issue 4's acceptance listed a "side-income events" form, but the `side_income_event` table + endpoints are assigned to 4b. Building the form against a non-existent backing table would violate the serial `4 → 4b` order, so the form ships in 4b alongside its table. Issue 4 still delivers forms for cards, retirement accounts, career position, side-income **economics**, and 1099 deductions.

**Reasoning**: 17 near-identical entities make a factory the DRY/KISS choice (≈1500 lines of boilerplate avoided) while explicit schemas keep the finance validation boundary honest. Deriving only self-contained arithmetic keeps Issue 4 focused on CRUD without prematurely owning logic that belongs to the position/agent issues.

**Trade-offs**:
- The factory uses live Pydantic classes in handler signatures, so `routers/vault.py` must not use `from __future__ import annotations` (documented in-file).
- JSONB money breakdowns (side-income expenses, net-worth splits) are stored as Decimal-preserving strings because `EncryptedJSON` serializes with `json.dumps`; the Out schemas coerce them back to `Decimal` on read.
- New file `routers/vault_ui.py` (HTMX fragment endpoints) added to the canonical tree in `docs/SOT.md`.

**Verification**: 45/45 pytest pass against local Postgres 16 + Redis 7 (sandbox: venv + local `pg_ctl` cluster, registry-pulled docker unavailable). HTMX UI verified at the endpoint level via `TestClient`; full in-browser walkthrough + the <30 min/month timed measurement pending local `docker compose up` (Gate 2).

**Owner**: reesepludwick@gmail.com (approved 2026-05-25)

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

---

## 2026-05-24 — Encryption boundary: TypeDecorators + naming convention

**Context**: Issue 2 introduces the encryption boundary for sensitive vault data. Two approaches considered: (A) explicit `encrypt()`/`decrypt()` calls at the CRUD layer, (B) SQLAlchemy `TypeDecorator`s that transparently encrypt on write / decrypt on read at the ORM layer.

**Decision**: Use SQLAlchemy `TypeDecorator`s. Three types defined in `crypto.py`:
- `EncryptedString` — Python `str` ↔ Fernet-encrypted `bytea`
- `EncryptedNumeric` — Python `Decimal` ↔ Fernet-encrypted `bytea` (string-serialized Decimal under the hood; money is always `Decimal`, never `float`)
- `EncryptedJSON` — Python `dict` ↔ Fernet-encrypted `bytea` (JSON-serialized with `sort_keys=True` for determinism)

**Naming convention**: DB column name stays `<field>_encrypted` (matches `docs/SOT.md` data model, signals to DBAs which fields are encrypted at a glance). Python attribute uses the clean name. Example: `account.current_balance` is a `Decimal` in code; the DB column is `current_balance_encrypted` holding bytea. Mapped via SQLAlchemy's column-name override in `mapped_column("current_balance_encrypted", EncryptedNumeric())`.

**JSONB split by sensitivity**: native PG `JSONB` for non-sensitive metadata (card category multipliers, categorical tax treatment, career milestones). `EncryptedJSON` for sensitive payloads (audit-log before/after snapshots, net-worth asset/liability breakdowns, message vault-ref citations, pattern vault-refs).

**Reasoning**:
- TypeDecorator removes the entire class of "developer forgot to encrypt on this new endpoint" bugs — the safe path is the only path.
- Satisfies CLAUDE.md's "every sensitive-field read uses `decrypt()`" because the decoder does it transparently, every read.
- Keeps the key in env / app process — never touches the DB host's disk (unlike pgcrypto). Cleaner per `docs/THREAT_MODEL.md`.
- Split JSONB strategy pays encryption cost only where the threat model requires it.

**Trade-offs**:
- Encrypted columns can't be queried with WHERE clauses on their plaintext value (expected and desired — these are user-private balances, not search keys).
- Marginal CPU cost on every read (Fernet decrypt is microseconds; negligible at v1 scale).
- Custom TypeDecorator code (~30 lines) instead of a third-party library — `sqlalchemy-utils.EncryptedType` was considered and ruled out (AES-only, sleepy project).

**Owner**: reesepludwick@gmail.com (approved 2026-05-24)

---

## 2026-05-24 — Free-first data ingestion strategy (Plaid deferred indefinitely)

**Context**: After Issue 2 closed, owner clarified the operational reality: 10+ accounts total, $0/month tooling budget, mixed granularity (balance-only for cards/banks, transaction-level for side businesses), wants SoFi-style per-share investment tracking. Plaid pricing (~$15–30/mo at this account count) exceeds the budget. Manual entry is accepted as the primary mode.

**Decision**: Drop Plaid from the v1 critical path. Build a **free Tier-1 automation layer** that uses public free APIs (yfinance for stock/ETF prices, Zillow Zestimate for real estate values) on top of manual entry. Add CSV/OFX import as the bulk-loading shortcut where institutions support it. The agent works fully without any per-account OAuth.

*Schema additions:*
- `holdings` — per-share investment tracking (account_id FK, ticker, share_count_encrypted, cost_basis_encrypted, purchase_date, last_known_price, last_priced_at). Enables SoFi-style live portfolio value via daily price refresh.
- `side_income_event` — per-shift / per-session granularity for DoorDash, coaching, freelance. Rolls up to the existing `side_income_economics` period aggregates.

*Free integrations (Tier 1):*
- **`yfinance`** (or Alpha Vantage as fallback) — daily price refresh for distinct tickers in `holdings`. No auth, no cost.
- **Zillow Zestimate** — quarterly value refresh for each `real_estate` row's address. Free tier, rate-limited.

*Backlog changes:*
- New **Issue 4b** — Free data automation layer (holdings table + side_income_event + yfinance + Zestimate + on-demand refresh endpoints). Lands before Issue 5 so wealth_position can compute against live values.
- New **Issue 4c** — CSV/OFX import. Most banks/cards/brokerages export to CSV; bulk import is the primary aggregation tool in the absence of Plaid.
- **Issue 4** acceptance tightened: steady-state manual workload must be <30 min/month with the right forms (duplicate-last-entry, keyboard-only, batch entry for side-business sessions, sane defaults).
- **Issue 13 (Plaid)** demoted to "deferred indefinitely" — kept in the backlog as a documented escape hatch if the owner's budget tolerance changes; not assumed for v1.

*Plaid status*: documented option, not a roadmap commitment. If owner ever wants automated bank/card refresh, Issue 13 spec is preserved and ready to pick up.

**Reasoning**:
- Free APIs cover the highest-leverage automation: investment values (the part that changes fastest and matters most for net-worth trajectory) and real estate values (the part that's annoying to look up manually). Everything else manual is feasible at this account count.
- CSV import is a one-time engineering cost that pays back every month for the life of the product.
- Keeping Plaid in the backlog (not removing it) preserves optionality without committing to the ongoing cost.
- 10+ accounts at $0/month is a real constraint — many "personal CFO" products silently assume Plaid; designing around the constraint produces a more durable v1.

**Trade-offs**:
- More upfront work on the CSV importer and the vault entry forms (Issue 4 + 4c).
- No automatic transaction-level data for bank/card spend — must come from CSV upload or be skipped.
- yfinance is unofficial (Yahoo Finance reverse-engineered); could break. Alpha Vantage is the documented fallback. Both free.
- Zestimate accuracy varies by market; flag in the agent's response that the value is an estimate, not an appraisal.

**Owner**: reesepludwick@gmail.com (approved 2026-05-24)
