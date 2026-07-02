# vault — assessed 2026-07-02

Slice: `vault/models.py`, `vault/schemas.py`, `vault/crud.py`, `vault/financial_snapshot.py`,
`vault/income_position.py`, `vault/wealth_position.py`. This is the encrypted data layer.

## Findings

### Concurrency & scale
- [SEV1] models.py:45,98,99,306,387,410,450,484,489,573 — **10 foreign-key columns, none
  indexed** (only `Index` in the module is `ix_transactions_import_hash_notnull`, which is on
  `import_hash`, not on a FK). Bare FKs: `Card.account_id`, `Expense.account_id`,
  `Expense.card_id`, `SideIncomeEconomics.income_stream_id`, `Holdings.account_id`,
  `SideIncomeEvent.income_stream_id`, `ImportBatch.account_id`, `Transaction.account_id`,
  `Transaction.import_batch_id`, `IntakeSubmission.snapshot_id`. Two are used as per-request
  filters — `crud.py:842 list_holdings WHERE account_id` and `crud.py:896 list_side_income_events
  WHERE income_stream_id` — so they seq-scan today; the rest force a full-child-table scan on any
  parent DELETE (unindexed-FK lock escalation, and Postgres takes a stronger lock while it scans).
  | fix: add `__table_args__ = (Index("ix_holdings_account_id", "account_id"), ...)` (or a per-model
  `Index(...)`) for every FK column above; ship as one Alembic migration
  `CREATE INDEX CONCURRENTLY`.
- [SEV2] crud.py:108,151,194,237,280,323,366,409,452,495,538,581,624,667,710,753,796 — every
  `list_*` does an unbounded `select().order_by()` with no LIMIT/pagination
  (`result.scalars().all()`). Fine for the small domain tables at single-user scale, but
  `list_side_income_events` / any table fed by CSV import can grow without bound. | fix: add
  `limit`/`offset` params (default cap, e.g. 500) to the list helpers that back
  growth-unbounded tables.

### Security & compliance
- [SEV1] whole module — **no `user_id`/tenant column on any of the 20+ tables, and no CRUD query
  filters by owner.** `compute_wealth_position` / `compute_income_position` /
  `_compute_snapshot_data` (wealth_position.py:47, income_position.py:35, financial_snapshot.py:62)
  accept a `user_id: str` argument and then **silently ignore it** — every `select()` reads all
  rows. Documented single-user v1 (THREAT_MODEL scopes multi-user out), so not a live leak today,
  but this is a latent cross-tenant BLOCKER the instant a second user is added, and the accepted-
  but-unused `user_id` is a trap that reads as "already scoped." | fix: before any second user, add
  a `user_id` column + FK to every table, filter every query, and add a regression test that
  tenant B cannot read tenant A. Until then, either wire `user_id` into the WHERE clauses or drop
  the parameter so it doesn't imply isolation that isn't there.
- [SEV2] models.py:34 — `Account.plaid_account_id` stored as plaintext `String(128)`. THREAT_MODEL
  §4 mandates account identifiers be redacted at the API boundary; the Plaid item/account id sitting
  in cleartext in a DB dump is an identifier leak (the access token at
  `plaid_access_token_encrypted` is correctly handled elsewhere). | fix: move to an
  `EncryptedString()` column, or store only a last-4/opaque reference.
- Encryption coverage is otherwise strong: every balance / comp / APR / amount / AGI /
  net-worth column uses `EncryptedNumeric`, addresses and prep-notes use `EncryptedString`, and
  breakdown/analysis/intake blobs use `EncryptedJSON`. Decryption is transparent via the
  TypeDecorators on ORM attribute read — no manual `decrypt()` gaps found.
- Audit `before_jsonb`/`after_jsonb` correctly land in `EncryptedJSON` columns, so the decrypted
  balances captured by `_row_snapshot` (crud.py:68) are re-encrypted at rest — good.
- Loggers at crud.py:59 and financial_snapshot.py:26 are defined but never emit — no
  sensitive-field log leakage in this slice. (ok)

### Domain correctness
- [SEV1] `_to_monthly` is defined **three times with divergent constants**:
  financial_snapshot.py:327 uses `weekly=4.333, biweekly=2.167` and has **no** `semimonthly`/
  `annually`/`yearly` keys and no `.lower()`; income_position.py:173 and wealth_position.py:221 use
  `weekly=4.33, biweekly=2.17, semimonthly=2` + case-folding. Same input cadence therefore yields
  different monthly figures depending on which module computes it (e.g. a `"semimonthly"` or
  `"Annual"` expense falls through to the ×1 default in `financial_snapshot` but not in the
  position modules), so `total_monthly_expenses` on the snapshot can disagree with the ladder math
  it is built from. | fix: extract one `to_monthly(amount, cadence)` into a shared
  `vault/_money.py` (single canonical mapping, case-folded) and import it in all three modules.
- [SEV2] financial_snapshot.py:119,138,279 — `k401_match_capture_pct` is initialized to `None`,
  the comment says "computed below if benchmark data available," but it is **never computed** and
  always persists as `NULL`; `k401_match_pct_offered` (line 119) is likewise a dead placeholder,
  and `k401_utilization_pct` (line 136) is computed then discarded (never returned). Any consumer
  of the snapshot's 401k-match metric silently gets null. | fix: either implement the match-capture
  calc or remove the column + field so the null isn't mistaken for "0% captured."
- [SEV2] financial_snapshot.py:133,137 — HSA utilization always divides by
  `HSA_LIMIT_SINGLE_2026`; `HSA_LIMIT_FAMILY_2026` is imported (line 19) but never used, so a
  family-plan user's HSA utilization is overstated (~1.9x). `has_hsa_eligible_plan` is a bool with
  no single/family discriminator. | fix: add a coverage-tier field and select the family limit when
  applicable.
- [SEV2] financial_snapshot.py:54 — `analysis_jsonb=data` where `data` still holds **raw `Decimal`**
  values at the top level (`net_worth`, `total_assets`, `savings_rate_pct`, etc.); only the nested
  detail lists were coerced to `float`. If `EncryptedJSON`'s serializer uses stock `json.dumps` it
  raises `TypeError: Object of type Decimal is not JSON serializable` at flush.
  (needs-runtime-confirmation — serializer lives in `crypto.py`, out of slice.) | fix: coerce the
  top-level Decimals to `str`/`float` before assignment, or confirm `EncryptedJSON` has a Decimal
  default; add a test that stores a snapshot end-to-end.

### Resource lifecycle
- [SEV2] financial_snapshot.py:39-58 — `compute_and_store_snapshot` does `session.add(snap)` +
  `flush()` (a vault mutation) but writes **no audit-log row**, unlike every path in crud.py.
  CLAUDE.md requires an audit row for every vault mutation. | fix: call
  `write_audit_log(session, actor, "create", "financial_snapshot", snap.id, None, ...)`. (Snapshot
  is derived data, so this may be a deliberate exemption — if so, document it in DECISIONS.md.)
- CRUD helpers correctly take an injected `AsyncSession` and leave commit to the caller
  ("Callers are responsible for committing" — crud.py:7); no session is opened/leaked here. `delete_*`
  writes the audit row *before* `session.delete()` so the row still exists for the snapshot — good.
  Note: no `ondelete` cascade is configured, so deleting a parent (e.g. an `Account` with non-null
  `Holdings.account_id`) raises IntegrityError at commit — acceptable, but see FK-index finding for
  the scan cost of that constraint check. (ok, with caveat)

### Cleanliness & typing
- [cleanup] financial_snapshot.py:32 — ruff F821 "Undefined name FinancialSnapshot" is a **false
  alarm at runtime**: `from __future__ import annotations` (line 7) makes the return annotation the
  string `"FinancialSnapshot"`, which is never evaluated; the name is also imported locally at
  line 34. No NameError. | fix (to silence the linter): import the model under
  `if TYPE_CHECKING:` at module top and drop the quotes, or `# noqa: F821`.
- [cleanup] crud.py:10,61 — `M = TypeVar("M")` and the `TypeVar` import are dead (never used). |
  fix: delete both.
- [cleanup] crud.py — the 20 entity CRUD blocks are ~30 lines of identical boilerplate each
  (get → `_row_snapshot` → setattr loop → flush → audit). Heavy DRY violation. | fix: a generic
  `create/update/delete(session, Model, entity_type, ...)` factory would collapse ~600 lines to
  ~80; weigh against KISS/readability, but the current copy count is well past the threshold.
- [cleanup] income_position.py:29-32, wealth_position.py:30-37 — `income_ladder`/`open_gaps` typed
  as bare `list` inside the TypedDicts; should be `list[IncomeStep]` / `list[AllocationGap]`.
- [cleanup] models.py:396-398 — `Holdings.last_known_price` uses `EncryptedNumeric` (value IS
  encrypted) but the DB column name lacks the `_encrypted` suffix that the module docstring says
  marks ciphertext columns; a dump/migration reader would misread it as plaintext. | fix: rename
  the column to `last_known_price_encrypted` in a migration for convention consistency.
- [cleanup] financial_snapshot.py:19 — `HSA_LIMIT_FAMILY_2026` imported but unused (see HSA
  finding); `MILEAGE_RATE_2026` is used, ok.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | 1 SEV2 (snapshot mutation not audited); sessions caller-managed, ok |
| 2 Concurrency & scale | 1 SEV1 (10 unindexed FKs), 1 SEV2 (unbounded list) |
| 3 Security & compliance | 1 SEV1 (no tenant column, user_id ignored), 1 SEV2 (plaid_account_id plaintext); encryption coverage otherwise strong |
| 4 Domain correctness | 1 SEV1 (divergent `_to_monthly`), 3 SEV2 (k401 null, HSA family, Decimal jsonb) |
| 5 LLM SDK | n/a (no LLM in this module) |
| 6 Cleanliness & typing | 6 cleanup (F821 false alarm, dead TypeVar, CRUD boilerplate, bare list types, column naming, unused import) |
| 7 Error handling / API | n/a (data layer, not a router) |
| 8 Config & paths | n/a (no paths/config; encryption key sourced in crypto.py, out of slice) |

## Module verdict
NEEDS-WORK — no live BLOCKER at single-user v1, but the 10 unindexed FKs, the divergent
`_to_monthly` math, and the accepted-but-ignored `user_id` (a cross-tenant BLOCKER the moment a
second user exists) must be fixed before scale or public launch. The known F821 is a linter false
positive, not a runtime NameError.
