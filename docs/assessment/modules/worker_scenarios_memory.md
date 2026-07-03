# worker + scenarios + memory — re-assessed 2026-07-02 (post-remediation)

Re-verification of the original 2026-07-02 findings against current code on branch
`hardening/phase-7-finish-line`. Each finding is marked **FIXED / OPEN / DEFERRED** with
file:line evidence.

Legend: DEFERRED = intentionally out of scope for Road A (single-container / single-user),
documented in the Road-B backlog — not a live bug.

---

## worker (`worker/cron.py`)

| # | Sev | Finding | Status | Evidence |
|---|-----|---------|--------|----------|
| 1 | SEV1 | Weekly digest has no idempotency guard / leader election → double-send under multi-replica | **DEFERRED (documented)** | Single in-process `AsyncIOScheduler` with one job, no distributed lock: `cron.py:53-66`. Road A is explicitly single-container/single-replica; deferral documented at `docs/PRODUCTION_ROADMAP.md:160`, `docs/DECISIONS.md:85`, `docs/assessment/modules/worker.md:11-12`, `docs/assessment/REPORT.md:63,92`. Confirmed a deliberate Road-B deferral, not a live bug on the documented deploy. |
| — | SEV2 | `misfire_grace_time` + `coalesce` added to digest job | **FIXED** | `misfire_grace_time=3600` at `cron.py:64`; `coalesce=True` at `cron.py:65`. Matches expected. |
| — | SEV2 | Digest wrapped in `asyncio.wait_for` timeout | **FIXED** | `_DIGEST_TIMEOUT_SECONDS = 300` at `cron.py:20`; `await asyncio.wait_for(generate_and_send_digest(), timeout=_DIGEST_TIMEOUT_SECONDS)` at `cron.py:27`, with `TimeoutError` logged at `cron.py:28-29`. Matches expected (300s). |
| — | cleanup | `httpx` client hoisted to module singleton | **FIXED** | Module-level `_http: httpx.AsyncClient | None = None` at `cron.py:18`; lazily created once and reused across pings at `cron.py:41-45`. Matches expected. |

**worker verdict:** All remediation items FIXED. The one remaining SEV1 (idempotency/leader
election) is a correctly-documented Road-B/multi-replica deferral — production-ready for the
single-container Road-A deploy.

---

## scenarios (`scenarios/models.py`, `scenarios/engine.py`)

| # | Sev | Finding | Status | Evidence |
|---|-----|---------|--------|----------|
| 2 | SEV2 | Money fields accept negatives (no validation) | **FIXED** | `@field_validator("current_amount", "monthly_contribution", "current_monthly_income")` rejects `v < 0` with `ValueError("must be non-negative")` at `models.py:34-42`; `@field_validator("target_amount")` rejects `v <= 0` at `models.py:44-49`. `delta_monthly` intentionally excluded (a cut is a valid negative — comment at `models.py:39`). `annual_return_pct` bounded 0–50 at `models.py:27-32`. Engine also defends target at `engine.py:30-31`. Matches expected exactly. |

**scenarios verdict:** FIXED — negative/invalid money inputs now fail at the Pydantic boundary
(422) rather than producing nonsensical projections. Production-ready.

---

## memory (`memory/models.py`, `memory/retrieval.py`)

| # | Sev | Finding | Status | Evidence |
|---|-----|---------|--------|----------|
| 3 | SEV2 | `Message.conversation_id` unindexed | **FIXED** | `op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])` at `migrations/versions/d4e7f2a1b9c3_...py:60` (down-rev drop at :92). Column defined `memory/models.py:32`. |
| 3 | SEV2 | `Pattern.detected_at` unindexed | **FIXED** | `("ix_patterns_detected_at", "patterns", ["detected_at"])` at `migrations/versions/a7e3f9c21b84_add_missing_fk_sort_indexes.py:26`. Sort query at `retrieval.py:91-96`. |
| 3 | SEV2 | `FinancialSnapshot.computed_at` unindexed | **FIXED** | `("ix_financial_snapshots_computed_at", "financial_snapshots", ["computed_at"])` at `migrations/versions/a7e3f9c21b84_...py:27`. Sort query at `retrieval.py:109-112`. |
| 4 | SEV1 | No `user_id` on memory tables (cross-tenant leak at 2nd user) | **DEFERRED (documented)** | `memory/models.py` has no `user_id` column on any of `Conversation`/`Message`/`Decision`/`Pattern`; `build_retrieval_context(session, user_id)` accepts but does not filter by `user_id` (`retrieval.py:45`, queries at `:71-76,:91-96,:109-112` unscoped). Documented single-user deferral: `docs/assessment/REPORT.md:64`, `docs/assessment/modules/memory.md:8`, `docs/assessment/modules/routers.md:19`, `docs/DECISIONS.md:85,97`. Confirmed deferral, not a live bug for single-user v1. |
| 5 | cleanup | Unused `import math` in retrieval.py | **FIXED** | No `import math` remains; imports are `json`, `datetime…`, `Decimal, ROUND_CEILING`, `select`, `AsyncSession`, `logging` (`retrieval.py:8-15`). `ruff check` passes clean on all four files. |
| 5 | cleanup | Dead empty classes in retrieval.py | **OPEN (minor)** | `_WealthPositionContract` (`retrieval.py:37-38`) and `_IncomePositionContract` (`retrieval.py:41-42`) are still present — docstring-only classes with no attributes, referenced nowhere (grep: definitions only). Ruff does not flag them (they carry docstrings), so ruff=0 does not cover this. Cosmetic; the bridge logic uses plain dicts (`retrieval.py:185-237`), so the "contract" classes serve only as documentation stubs. |

**memory verdict:** All three index findings FIXED; `user_id` is a correctly-documented Road-B
deferral. One residual cosmetic OPEN item (two dead docstring-only classes). Production-ready
for single-user scope.

---

## Combined module verdict

**READY (Road A, single-container / single-user).** Every actionable SEV2 remediation across
worker, scenarios, and memory is FIXED with matching evidence, and both SEV1 items
(digest idempotency/leader-election, memory `user_id`) are confirmed deliberate,
documented Road-B deferrals rather than live bugs. The only residual is one cosmetic OPEN
cleanup item (two dead docstring-only classes in `retrieval.py:37,41`) that does not affect
correctness, security, or behavior.

**Counts (9 tracked items):** FIXED 6 · OPEN 1 · DEFERRED 2.
