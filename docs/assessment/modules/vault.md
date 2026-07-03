# vault — assessed 2026-07-03

Slice: `vault/{models,crud,schemas,wealth_position,income_position,financial_snapshot,_money}.py`
(+ `crypto.py` read only to verify the encryption boundary; it is another module's slice).

## Findings

- [SEV2] vault/wealth_position.py:42-46 — hardcodes year-versioned tax constants
  (`_IRA_ANNUAL=7000`, `_HSA_ANNUAL_SINGLE=4300`, `_401K_ANNUAL=23500`,
  `_HIGH_INTEREST_THRESHOLD=7`) that `financial_snapshot.py:22-26` already imports from
  `agent/principles.py`. CLAUDE rule: year-versioned tax constants live in `agent/principles.py`.
  Two sources → silent drift when principles roll to 2027 (ladder stays on 2026). | fix: delete the
  local constants and `from agent.principles import ROTH_IRA_LIMIT_2026, HSA_LIMIT_SINGLE_2026, ...,
  HIGH_INTEREST_APR_THRESHOLD`; reference those.
- [SEV2] vault/financial_snapshot.py:89-94 vs vault/wealth_position.py:204-220 vs
  vault/income_position.py:53-62 — the "sum Expense rows → monthly" loop is duplicated in three
  modules and has already DIVERGED: `wealth_position` and `income_position` floor the result at a
  `Decimal("3000")` fallback, but `financial_snapshot` does NOT. When the Expense table is empty,
  the snapshot reports `total_monthly_expenses=0` (→ `savings_rate=100%`, `emergency_months=None`)
  while the wealth ladder simultaneously shows a ~$9k emergency-fund gap off the 3000 floor —
  inconsistent user-facing numbers from one vault. | fix: extract
  `async def sum_monthly_expenses(session) -> Decimal` into a shared helper, decide the fallback
  once, and call it from all three.
- [SEV2] vault/financial_snapshot.py:167,176,183-185,196,204,209 — nested money in
  `analysis_jsonb` is cast to `float(...)` (monthly_gross, balances, apr, minimum_payment,
  net_hourly, goal target/current) before storage, contrary to the project's no-float-money rule.
  DECISIONS.md notes the Decimal→str concern was "resolved," but that resolution covers only the
  top-level `FinancialSnapshot` Decimal columns; these nested detail lists still serialize float.
  This payload is what the agent/LLM and UI reason over. | fix: keep `Decimal` (EncryptedJSON's
  `_json_default` already serializes Decimal→str) instead of `float(...)`; drop the float casts.
- [cleanup] vault/_money.py:13-23 — cadence factors are truncated decimals (`weekly 4.333`,
  `quarterly 0.333`, `annual 0.0833`) that systematically understate by ~0.04-0.1% (annual $120k →
  ~$119,952/yr reconstructed). Math is directionally correct and semimonthly=2 / biweekly=2.167 are
  right; only precision is lost. | fix: use exact ratios `Decimal(52)/Decimal(12)`,
  `Decimal(26)/Decimal(12)`, `Decimal(4)/Decimal(12)`, `Decimal(1)/Decimal(12)`.
- [cleanup] vault/models.py:396-398 — `Holdings.last_known_price` uses `EncryptedNumeric` (correctly
  encrypted) but the DB column is named `"last_known_price"`, violating the module's own documented
  "columns named `*_encrypted` store ciphertext" convention that every other encrypted column
  follows. Confusing for migrations/schema readers. | fix: rename the column to
  `"last_known_price_encrypted"` via an Alembic migration.
- [cleanup] vault/crud.py:61 — `M = TypeVar("M")` declared and never used; vault/crud.py:59 and
  vault/financial_snapshot.py:31 declare `logger` that is never called. | fix: delete the dead
  TypeVar and unused loggers.
- [cleanup] vault/wealth_position.py:67-101,223-237,288-301 — the `Account` table is fully scanned
  three separate times inside one `compute_wealth_position` call (assets, cash, brokerage), and
  `Expense` is re-scanned across all three position modules; the snapshot pipeline issues ~15
  SELECTs, several re-reading the same table. Harmless at single-user Road A row counts but
  redundant. | fix (portfolio polish): load each table once and partition in Python.
- [cleanup] vault/models.py:436-443 — `AuditLog` immutability is enforced only via ORM
  `before_update`/`before_delete` mapper events; a Core/bulk `update()`/`delete()` or raw SQL would
  bypass them. Fine for the current all-ORM CRUD path. | fix (defense-in-depth): add a Postgres
  `REVOKE UPDATE, DELETE` / trigger on `audit_log` in a migration.

## Acknowledged / documented — NOT flagged
- `Account.plaid_account_id` plaintext (models.py:34) — DECISIONS.md 2026-07-02: encryption deferred
  to Phase 5; Plaid deferred indefinitely so the column is always empty. Verified: every other
  sensitive *value* column (balances, APR, comp, contributions, cost basis, AGI, audit before/after
  JSON, breakdown JSON) IS encrypted via the crypto.py TypeDecorators.
- `Transaction.description`/`notes`/`category` plaintext (models.py:487-493) — DECISIONS.md
  b5e2a9c3f107: transactions deemed non-private at the value level, hash is the sensitivity
  boundary; `amount` is in fact encrypted (stricter than the decision text).
- `k401_match_capture_pct` always `None` (financial_snapshot.py:145,286) — documented NULL
  placeholder in DECISIONS.md; the "computed below" comment is stale but the behavior is intended.
- Unbounded `list_*` (no LIMIT) in crud.py — DECISIONS.md defers pagination caps to Phase 4b/5;
  bounded by single-user data.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | ok — session passed in by caller (unit-of-work), commit documented as caller's job; no client construction; no leak paths |
| 2 Concurrency & scale | ok for Road A — no blocking calls in async paths; redundant table scans + unbounded lists noted as cleanup, pagination deferral documented |
| 3 Security & compliance | ok — all sensitive value columns encrypted at the TypeDecorator boundary; audit before/after stored via EncryptedJSON; no sensitive data in any log (loggers unused); plaintext fields all documented decisions on empty/non-private columns |
| 4 Domain correctness (money) | 3 findings — DRY tax-constant drift, diverged expense fallback, float money in payload; Decimal used for all stored columns; cadence math correct if imprecise |
| 5 LLM SDK | n/a (no LLM in vault — pure deterministic data logic) |
| 6 Cleanliness & typing | cleanups — dead TypeVar/loggers, duplicated expense loop, column-naming convention break; signatures otherwise well typed |
| 7 Error handling / API | n/a (not a router; no request/response surface) |
| 8 Config & paths | n/a (no paths/config in slice; encryption key handled in crypto.py/config.py) |

## Module verdict
NEEDS-WORK — no BLOCKER or SEV1; encryption and lifecycle posture is solid and the flagged plaintext
fields are all documented decisions on empty/non-private columns, but three SEV2 money/DRY defects
(duplicated tax constants with drift risk, diverged expense-fallback producing inconsistent snapshot
vs ladder numbers, float money in the analysis payload) should be fixed before it reads as
senior-polished.
