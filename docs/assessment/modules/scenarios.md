# scenarios — assessed 2026-07-02

Slice: `scenarios/engine.py`, `scenarios/models.py` — deterministic forward-projection
math (time-to-target compounding + income-change). Pure functions; no DB, no LLM, no
async, no external clients, no logging.

## Findings
- [SEV2] scenarios/models.py:14-25 — money fields (`current_amount`,
  `monthly_contribution`, `target_amount`, `current_monthly_income`,
  `delta_monthly`) accept any `Decimal` with no non-negative validation. Only
  `annual_return_pct` and (imperatively, in engine.py:30) `target_amount<=0` are
  guarded. A negative `current_amount` projects from a negative balance; a negative
  `current_monthly_income` inverts the `change_pct` sign (engine.py:148) and produces
  a misleading percent; a negative `monthly_contribution` silently returns
  `not_reachable`. In a finance tool these silently yield nonsensical numbers rather
  than a clear error | fix: add `@field_validator` on `current_amount`,
  `monthly_contribution`, `current_monthly_income` asserting `>= 0`, and move the
  `target_amount > 0` rule into a validator on the model so bad input fails at the
  boundary (422) instead of mid-computation; keep `delta_monthly` free to be negative
  by design and document that.
- [SEV2] scenarios/engine.py:38 — `requires_disclaimer = annual_pct > 0` suppresses
  the disclaimer at exactly 0% return, yet the result `message`/`reasoning` still
  frame the projection as "annual return" investment growth (engine.py:61-64).
  Defensible as a pure-cash savings case, but the wording implies investing. Per
  CLAUDE.md the disclaimer is mandatory on anything "touching investment specifics" |
  fix: either (a) always attach the disclaimer for `time_to_target`, or (b) reword the
  0%-return message/reasoning to "savings (no growth assumed)" so the framing matches
  the no-disclaimer decision. Product call — confirm with owner.
- [cleanup] scenarios/engine.py:37 & :102 — the monthly-rate formula
  `annual_pct / 100 / 12` is computed twice (once for display in `_time_to_target`,
  once for the loop in `time_to_target`), DRY | fix: extract
  `_monthly_rate(annual_pct: Decimal) -> Decimal` and call it from both.
- [cleanup] scenarios/engine.py:137-159 — `income_change(...) -> dict` is loosely
  typed; the returned dict mixes `Decimal` values under fixed keys | fix: declare a
  `TypedDict` (e.g. `IncomeChangeResult`) or annotate `-> dict[str, Decimal]`.
- [cleanup] scenarios/models.py:37,39 — `ScenarioOutput.result: dict` and
  `assumed_constants: dict` are bare `dict`; annotate `dict[str, object]` for the type
  checker.

## Notes (verified correct — not findings)
- Compounding is correct and internally consistent: ordinary-annuity convention
  `balance = balance*(1+r) + contribution` applied at end of each month, matching the
  reasoning trace (engine.py:66-70, :99, :105). No off-by-one: the `current >= target
  → months=0` short-circuit (engine.py:32-33) means `time_to_target` is only entered
  when `current < target`, and its loop runs `range(1, max_months+1)` returning the
  first month `balance >= target` — consistent.
- Money math uses `Decimal` end-to-end in both core loops; `float()` appears only for
  display strings (engine.py:57,68,78) — no lossy float in load-bearing money paths.
- Division-by-zero is guarded everywhere it could occur: `change_pct` guards
  `current_monthly != 0` (engine.py:150); no division by user-controlled zero elsewhere
  (`r` may be 0 but is never a divisor).
- Horizon is bounded: `_MAX_MONTHS = 600` caps the loop at 600 iterations; over 600
  Decimal iterations precision is non-lossy (28-digit context). Stateless pure
  functions — thread-safe, no shared mutable state, no unbounded accumulation.
- Config: engine uses no tax constants — `_MAX_MONTHS` is a projection-horizon ceiling
  (not a tax constant), and `annual_return_pct` is user input, so there is nothing that
  should trace to `agent/principles.py`. No hardcoded-tax-constant violation.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | n/a (pure functions; no DB/clients/temp files) |
| 2 Concurrency & scale | ok (bounded 600-iter horizon, stateless, sync-only) |
| 3 Security & compliance | ok (no logging, no secrets/PII, no SQL) |
| 4 Domain correctness | 2 SEV2 (missing input bounds; 0%-return disclaimer framing); core math verified correct |
| 5 LLM SDK | n/a (no LLM in this module) |
| 6 Cleanliness & typing | 3 cleanup (DRY rate formula, loose dict return types) |
| 7 Error handling / API | n/a (not a router; `ValueError` on invalid target is appropriate for the boundary above to map to 422) |
| 8 Config & paths | ok (no tax constants, no paths, horizon ceiling is local) |

## Module verdict
NEEDS-WORK — projection/compounding/Decimal math is correct and bounded; the gaps are
missing non-negative input validation on money fields and a borderline 0%-return
disclaimer framing, plus minor DRY/typing cleanups. No BLOCKER, no SEV1.
