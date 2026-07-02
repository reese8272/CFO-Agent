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

## 2026-07-02 — Phase 6 agent correctness: proposals reducer + multi-specialist routing (CONTRACTS §1 amendment)

**Context**: The assessment found the agent graph doesn't do what its design says — routing fired
only ONE specialist (the `operator.add` fan-out and `turn_kind="both"` were dead), and the Coach's
additive re-emit *duplicated* proposals reaching the Synthesizer.

**Decision (amends CONTRACTS.md §1)**:
- **`proposals` reducer changed from `operator.add` to `merge_proposals`** (replace-by-`node`). This
  is the one CONTRACTS.md §1 amendment. Parallel specialists still accumulate (distinct nodes); the
  Coach now *replaces* by node instead of appending a second enriched copy. The `NodeProposal` shape
  is unchanged.
- **`_route_from_analyzer` returns a `list[str]`** so LangGraph fans out to every routed specialist
  (a "both" turn runs Strategist AND Income-Optimizer, etc.), converging on Coach. Was a single-node
  return (top-priority only).
- **Coach tool extraction guarded** + `MAX_TOKENS 512 → 2048` (array output truncated multi-specialist
  turns → could 500); falls back to raw proposals on truncation.
- **`leverage_score` clamped to 0.0–1.0** in strategist/career/tax_optimizer/coach (income_optimizer
  already did); legacy `anthropic-beta: prompt-caching-2024-07-31` header dropped (GA).
- **Tax quarterly-estimate 22% bracket** → year-stamped `ASSUMED_FED_MARGINAL_BRACKET_2026` in
  `principles.py` (documented assumption; deriving from AGI deferred).

**Owner**: reesepludwick@gmail.com (approved 2026-07-02)

---

## 2026-07-02 — Phase 4 data-layer: index scope correction + plain create_index + deferrals

**Context**: The assessment flagged "10 unindexed FK columns" and the roadmap prescribed a
`CREATE INDEX CONCURRENTLY` migration. Investigating before writing it revealed the finding was
partly inaccurate.

**Decisions**:
- **Index scope corrected to 5, not 10.** Migration `d4e7f2a1b9c3` already indexed 7 of the flagged
  FKs, and `ix_side_income_events_stream_occurred` already leads with `income_stream_id`. The
  assessment subagent read `models.py` (no `index=True` declared) and missed the migration-level
  indexes — model-vs-migration drift, not missing indexes. New migration `a7e3f9c21b84` adds only
  the genuinely-missing 5: `expenses.card_id`, `side_income_economics.income_stream_id`,
  `intake_submissions.snapshot_id`, `patterns.detected_at`, `financial_snapshots.computed_at`.
- **Plain `op.create_index`, not `CONCURRENTLY`** — tiny single-user tables, matches the `d4e7`
  precedent, and the `SET LOCAL lock_timeout='30s'` (Phase 2) bounds contention. Sidesteps the
  CONCURRENTLY-in-a-transaction problem, which only matters for large tables.
- **`_to_monthly` unified** into `vault/_money.py` from 3 divergent copies; canonical uses the more
  precise 4.333 / 2.167 factors + full cadence set + case-folding (tiny accuracy shift for
  income/wealth position, which were 4.33 / 2.17).
- **HSA family limit via `household_size` proxy** (no single/family coverage field exists; adding
  one would need a schema migration for marginal value).
- **`analysis_jsonb` Decimal concern was already handled** — `EncryptedJSON` serializes Decimal→str
  (Issue-16 fix); the assessment's `(needs-runtime-confirmation)` resolved to a non-issue.

**Deferred to Phase 4b / 5**: list-endpoint pagination caps (SEV2 bounded-work; doesn't bite at
single-user scale) and `Account.plaid_account_id` encryption (Phase 5 security; Plaid deferred so
column is empty). `k401_match_capture_pct` left as a documented NULL placeholder.

**Owner**: reesepludwick@gmail.com (approved 2026-07-02)

---

## 2026-07-02 — Public launch as "Road A" portfolio / single-user (not multi-tenant SaaS)

**Context**: Owner decided to make the project public (GitHub / LinkedIn) and asked for a "100%
production" plan. A full production assessment (`docs/assessment/REPORT.md`) surfaced 1 BLOCKER,
~20 SEV1s, and a large latent tenant-isolation gap (no `user_id` column or owner filter anywhere).
The scope of "public" changes whether that gap is a BLOCKER or a deferred item.

**Decision**: Ship **Road A** — public *code* + self-hosted *single-user* (one operator). In scope:
the disclaimer BLOCKER, rate limiting, LLM/external timeouts, async-loop hygiene, secrets & CVE'd-
dependency hygiene, FK indexes + pagination, money-math correctness, prod hardening, and agent-
design correctness. **Out of scope for Road A**: multi-tenant isolation (`user_id`/RLS, per-user
quotas, OAuth2, ToS/Privacy, erasure endpoint), which stays the documented Pre-GA / Road-B backlog.
The finish line is `/assess` → PRODUCTION-READY — YES (Road A). Sequenced in `docs/PRODUCTION_ROADMAP.md`
(supersedes the old Issue #28 P2 hardening).

**Reasoning**: Road A is the highest-value résumé artifact per unit of effort and is reachable in a
focused multi-phase sprint; the single-user constraint is honest to the current auth model and is
itself a defensible design decision to present. Promoting tenant isolation to a BLOCKER now would
balloon scope into a real multi-tenant product (OAuth2, RLS, quotas, legal) with no second user to
justify it.

**Trade-offs**: The public repo ships with tenant isolation absent by design — must be called out
explicitly in the README so it reads as a deliberate v1 boundary, not an oversight. Inviting any
real second user later requires the full Road-B block before launch.

**Owner**: reesepludwick@gmail.com (approved 2026-07-02)

---

## 2026-05-27 — Issue 16: Secrets & deploy operations hardening

**Context**: Owner pain points — too many keys with unclear purpose, no way to troubleshoot a credential without seeing its value, scattered SSH keys, and deploys that failed/timed out. On checking out `main`, much of the ops scaffolding already existed (GHCR pipeline, `ENV_CHECKLIST.md`, `check_env.py`, `audit_secrets.py`); both CI and Deploy were red.

**Decisions**:
- **Secrets source of truth = Bitwarden (free) + `docs/ENV_CHECKLIST.md` registry.** GitHub Actions secrets are write-only and cannot be a system of record. Chosen over SOPS+age (added a tool/key to learn; owner wanted clarity over machinery). `VAULT_ENCRYPTION_KEY` kept in 3 copies / 2 formats (Bitwarden + second store + paper) because it is irreplaceable.
- **Deploy image = build in CI → GHCR → pull on VM** (already implemented on `main`; ratified). Build-on-host ruled out (OOM/slow on the free ARM VM).
- **Container recovery stack = `restart: unless-stopped` + Docker `healthcheck` + `willfarrell/autoheal` + optional Healthchecks.io dead-man's-switch** (`HEALTHCHECK_PING_URL`). Uptime Kuma ruled out (dies with the VM); GH-Actions-cron ruled out as primary (5-min floor, no alerting).
- **Troubleshooting = `check_env.py --live`** makes the cheapest real call per credential (Anthropic auth, Postgres `SELECT 1`, Redis `PING`, Fernet round-trip, SMTP login) and reports PASS/FAIL without ever printing the value.

**Fixes made**: 9 red CI tests repaired — `EncryptedJSON` now serializes `Decimal`; `_round100` ceilings; `EXPECTED_TABLES` synced; and a real income bug where `compute_income_position` summed `monthly_actual` across ladder steps (triple-counting a single income). Deploy gate fixed — `audit_secrets.py` no longer rejects `deploy.yml`'s `JWT_SECRET_KEY="auto-generated-per-deploy"` sentinel. Deleted clutter secrets `VAULT_ECRYPTION_KEY` (typo) and the vestigial Production `JWT_SECRET_KEY`.

**Deferred**: `docker-compose.prod.yml` override to drop the bind mount + `--reload` so the GHCR image is authoritative; a re-encryption helper for the key-rotation runbook.

**Owner**: reesepludwick@gmail.com (approved 2026-05-27)

---

## 2026-05-25 — Issue 14: audit log actor passed as User ORM object (bug fix)

**What changed**: All 57 `actor=user` call sites in `routers/vault.py` and `routers/holdings.py` changed to `actor=user.username`. The `vault/crud.py` signature declares `actor: str`; passing the ORM object caused `psycopg.ProgrammingError: cannot adapt type 'User'` at commit time.
**Why**: The router dependency `get_current_user` returns a `User` object. The original code passed it directly; the audit log's `actor` column (plain `String`) requires a scalar string.
**Source**: Issue 14 test run (2026-05-25) — error surfaced on first live-DB run of `test_holdings_crud`.
**Date**: 2026-05-25

---

## 2026-05-25 — AgentState extended with is_decision + decision_summary for Issue 9

**What changed**: Added `is_decision: bool` and `decision_summary: str | None` to the Synthesizer terminal output section of `agent/state.py`. Also added these fields to `RESPONSE_TOOL` in `agent/prompts.py` and to the synthesizer_node return dict.
**Why**: Issue 9 requires the Synthesizer to flag user-stated intents so persist_node can write Decision rows without a second LLM call. This is the minimal CONTRACTS.md amendment — no node I/O contracts change, only terminal fields added.
**Source**: Issue 9 approved approach (main conversation 2026-05-25).
**Date**: 2026-05-25

---

## 2026-05-25 — agent/state.py replaced with CONTRACTS.md-frozen version for Issue 7

**What changed**: The `agent/state.py` written in Issue 5 was a simplified scaffold (`WealthPosition` as full ladder, `IncomePosition` as full ladder, simple `AgentState`). Replaced with the CONTRACTS.md §1-frozen version: compact `WealthPosition`/`IncomePosition` (step/step_name/rationale/next_move only), `Annotated[list[NodeProposal], operator.add]` reducer for proposals, `NotRequired[dict]` for `net_worth_pace`, and all Synthesizer/Analyzer terminal output keys. The full-ladder types (`WealthLadder`, `IncomeLadder`, `AllocationGap`, `IncomeStep`) are now defined locally in `vault/wealth_position.py` and `vault/income_position.py` respectively. `memory/retrieval.py` bridges them to the compact AgentState types via `_bridge_wealth` and `_bridge_income`.
**Why**: Issue 7 requires the LangGraph `StateGraph(AgentState)` to use the frozen contract so downstream Issues 8/8b can be built in parallel against a stable state shape.
**Source**: CONTRACTS.md §1; Issue 7 build (2026-05-25).
**Date**: 2026-05-25

---

## 2026-05-25 — transactions table promoted to v1 for CSV/OFX import

**What changed**: Added `import_hash` (SHA-256 dedup key), `category`, `import_batch_id`, `notes` columns to the `transactions` table. The table was previously a stub ("Phase 2 — Plaid") in `docs/SOT.md` with no ORM model. Also added two new tables: `import_batches` (batch-level audit trail per upload) and `category_mappings` (learnable pattern-to-category classifier). `Transaction` ORM model created in `vault/models.py` with a unique constraint on `import_hash`.
**Why**: Issue 4c requires dedup-safe import; promoting the stub to a real table avoids creating a parallel shadow table. The stub schema (`posted_at`, `amount_encrypted`, `merchant`, `raw_payload_jsonb`) was replaced with a cleaner import-oriented schema — `occurred_at`, plain `Numeric` for `amount` (transactions are not user-private in the same way balances are; hash is the sensitivity boundary), `description`, `category`, `import_hash`, `import_batch_id`, `notes`. Migration `b5e2a9c3f107` guards against columns that may already exist for forward compatibility.
**Source**: Issue 4c approved approach (main conversation 2026-05-25).
**Date**: 2026-05-25

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

## 2026-05-25 — Property AVM: Zillow Zestimate → RentCast

**Context**: Issue 4b spec (and `docs/DECISIONS.md` entry 4 — "Free-first data ingestion strategy") named Zillow Zestimate as the free property value source. Pre-build research confirmed Zillow's public API has been fully dead since 2021; no individual-developer access path exists in 2026. Bridge Interactive (Zillow's successor API) is restricted to MLS-affiliated brokerages. Third-party Zillow-scraper wrappers on RapidAPI are legally grey, fragile, and violate ToS.

**Decision**: Replace Zillow Zestimate with **RentCast** (`rentcast.io/api`). Free tier: 50 calls/month, no credit card required. Endpoint: `GET https://api.rentcast.io/v1/avm/value?address=<addr>`. Returns `price`, `priceRangeLow`, `priceRangeHigh`. New env var: `RENTCAST_API_KEY` (optional — if absent, refresh endpoint returns 503 with a clear message; app still starts and runs).

Secondary option documented but not implemented: FHFA House Price Index (truly free, no API key) as a multiplier to inflate a known last-sale-price forward by metro appreciation rate. Deferred — requires the user to populate `purchase_price` and the FHFA metro code; adds complexity for uncertain accuracy gain at v1 scale.

**Reasoning**: RentCast is the current industry-standard free-tier AVM for individual developers in 2026. 50 calls/month is more than sufficient for a single-user tool refreshing a handful of properties once a month. The disclaimer requirement ("estimate, not an appraisal") applies equally to any AVM source.

**Trade-offs**:
- Requires a free RentCast account + API key (one-time setup, no ongoing cost).
- 50 calls/month cap — irrelevant at v1 scale (personal tool, handful of properties).
- RentCast may change free tier terms; FHFA HPI is the zero-dependency fallback if that happens.

**Source**: Pre-build research (2026-05-25) — Zillapi blog, Zillow Group developer docs, RentCast API docs, Homesage AVM comparison.

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
