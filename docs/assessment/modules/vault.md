# vault — re-assessed 2026-07-02 (post-remediation)

Branch: `hardening/phase-7-finish-line`. Each original 2026-07-02 finding re-verified
against current code with file:line evidence. Supersedes the pre-remediation
assessment of the same date.

---

## 1. [SEV1] "10 unindexed FK columns" — **FIXED**

Re-scoped and confirmed complete:

- New migration exists: `migrations/versions/a7e3f9c21b84_add_missing_fk_sort_indexes.py:22-28`
  adds the remaining 5 — `ix_expenses_card_id` (expenses.card_id),
  `ix_side_income_economics_income_stream_id` (side_income_economics.income_stream_id),
  `ix_intake_submissions_snapshot_id` (intake_submissions.snapshot_id),
  `ix_patterns_detected_at` (patterns.detected_at),
  `ix_financial_snapshots_computed_at` (financial_snapshots.computed_at).
  `down_revision = "d4e7f2a1b9c3"` chains correctly (line 18).
- Prior migration `d4e7f2a1b9c3` already indexed 7 FK columns
  (transactions.account_id, transactions.import_batch_id, cards.account_id,
  expenses.account_id, import_batches.account_id, holdings.account_id,
  messages.conversation_id) — `d4e7f2a1b9c3_*.py` upgrade() §3.
- `side_income_events.income_stream_id` is covered by the composite
  `ix_side_income_events_stream_occurred` on `["income_stream_id", "occurred_at"]`
  — `migrations/versions/a3f1c8d2e749_add_holdings_and_side_income_events.py:58-62`.
  A leading-column composite index serves single-column FK lookups, so no
  standalone index is needed.
- Index targets confirmed to exist: `patterns.detected_at` (`memory/models.py:62`),
  `financial_snapshots.computed_at` (`vault/models.py:519`).

## 2. [SEV1] `_to_monthly` defined 3× with divergent constants — **FIXED**

Single source of truth: `vault/_money.py:26` `to_monthly` (mapping `_MONTHLY_FACTORS`
at line 13, case-folded, full cadence vocabulary incl. semimonthly/annually/yearly).
Repo-wide grep for `def _to_monthly|def to_monthly` returns only this one definition.
All three consumers import it, no local defs:

- `vault/financial_snapshot.py:27` — `from vault._money import to_monthly as _to_monthly`
- `vault/income_position.py:19` — same import
- `vault/wealth_position.py:20` — same import

## 3. [SEV2] financial_snapshot HSA always uses SINGLE limit — **FIXED**

`vault/financial_snapshot.py:140-141`:
`_household = ... profile_row.household_size ...` then
`hsa_limit = Decimal(str(HSA_LIMIT_FAMILY_2026 if _household > 1 else HSA_LIMIT_SINGLE_2026))`.
Both constants imported at line 23; `agent/principles.py:13-14` defines
`HSA_LIMIT_SINGLE_2026 = 4_300` and `HSA_LIMIT_FAMILY_2026 = 8_550`.
`hsa_utilization_pct` (line 144) uses the household-appropriate denominator.

Residual (minor, not a regression of finding 3): the allocation-ladder step-3
*target* string in `vault/wealth_position.py:43` still hardcodes
`_HSA_ANNUAL_SINGLE = Decimal("4300")` and does not vary by household. Separate code
path from the corrected utilization math; display-only.

## 4. [SEV2] analysis_jsonb raw Decimal → possible TypeError — **FIXED (non-issue confirmed)**

`analysis_jsonb` is an `EncryptedJSON()` column (`vault/models.py:560`).
`EncryptedJSON.process_bind_param` serializes with
`json.dumps(..., default=_json_default)` (`crypto.py:101`), and `_json_default`
(`crypto.py:86-91`) maps `Decimal → str`. The dict assigned at
`vault/financial_snapshot.py:59` (with raw top-level `Decimal` values) therefore
serializes cleanly at flush — no TypeError. The separate `_hash_snapshot_data` path
has its own Decimal-safe `default` (`financial_snapshot.py:303-311`).

## 5. [SEV2, DEFERRED] Account.plaid_account_id stored plaintext — **DEFERRED (still open)**

Unchanged: `vault/models.py:34` — `plaid_account_id: Mapped[str | None] =
mapped_column(String(128), nullable=True)`, plaintext (not `EncryptedString`). Plaid
remains unused — only schema pass-through (`vault/schemas.py:34,43`) and the initial
migration column (`ed987c277fa9_initial_schema.py:32`); no ingest code writes it.
Correctly deferred to Phase 5b.

## 6. [SEV2, DEFERRED 4b] crud `list_*` unbounded — **DEFERRED (still open)**

Unchanged: every `list_*` in `vault/crud.py` issues `select(...).order_by(...)` with
no `.limit()`/pagination (e.g. `list_accounts` :108-110, `list_side_income_events`
:893-898, `list_holdings` :839-844). Acceptable at single-user scale; deferred per 4b.

## 7. [SEV1, DEFERRED Road B] no user_id/tenant column — **DEFERRED (still open)**

Unchanged: no `user_id`/tenant column on any model in `vault/models.py`. The
position/snapshot functions accept `user_id: str` but never filter on it
(`financial_snapshot.py:37`, `wealth_position.py:49`, `income_position.py:37`) — the
accepted-but-ignored param remains. Documented single-user deferral to Road B
multi-tenant work.

---

## Residual items observed (adjacent to original findings, still OPEN)

Not in the seven-item re-scope, but confirmed unchanged and worth carrying forward:

- [SEV2] `k401_match_capture_pct` is initialized to `None` with comment "computed
  below if benchmark data available" and is still **never computed**
  (`financial_snapshot.py:145,286`); persists as NULL.
- [SEV2] `compute_and_store_snapshot` performs a vault mutation (`session.add` +
  `flush`, `financial_snapshot.py:62-63`) but writes **no audit-log row**. May be a
  deliberate derived-data exemption — if so, record in `docs/DECISIONS.md`.

---

## Module verdict

**PASS (post-remediation) for personal-only v1.** All three actionable findings
(1 FK indexes, 2 `_to_monthly` unification, 3 HSA family limit) are FIXED with code
evidence; finding 4 is confirmed a non-issue. The three remaining listed items
(5 plaid plaintext, 6 unbounded lists, 7 no tenant column) are all pre-agreed
single-user DEFERRALs, none blocking at current scope. Two adjacent SEV2 residuals
(k401 null, snapshot not audited) remain OPEN but are non-blocking.

Counts: 3 FIXED + 1 FIXED(non-issue) / 3 DEFERRED / 0 newly regressed
(2 non-scoped residuals still OPEN).
Top remaining item: verify a tenant `user_id` column + query filters before any
second user (finding 7, the latent cross-tenant BLOCKER).
