# worker_scenarios_memory — assessed 2026-07-03

## Findings

- [SEV2] worker/cron.py:41-43 & digest.py:137 — the weekly-digest job is **not
  idempotent**: nothing records "digest already sent for ISO-week N". A single
  in-process `AsyncIOScheduler` fires the cron once (memory jobstore, no
  at-least-once redelivery), and `coalesce=True` + `misfire_grace_time=3600`
  correctly collapse a restart-near-07:00 backlog into one run — so the
  in-process risk is genuinely low. But `POST /digest/run-now` (routers/digest.py)
  shares the same `generate_and_send_digest()` with **no guard**, so a manual
  run plus the cron (or a second app replica running its own scheduler) sends two
  emails. Blast radius is a duplicate email only — no data mutation, no
  corruption. | fix: gate `generate_and_send_digest()` on a small sent-log row
  keyed on `year-week` (INSERT … ON CONFLICT DO NOTHING; skip send if the row
  already exists), or accept it explicitly with a DECISIONS.md note that the
  single-container Road-A deployment makes dedup unnecessary.

- [SEV2] worker/cron.py:41-47, 87-92 — the module-level `_http` httpx.AsyncClient
  created lazily in `_ping_healthcheck` is **never closed**. `stop_scheduler()`
  shuts the scheduler and nulls `_scheduler` but leaves `_http` open, leaking the
  client's connection pool on every app shutdown / test lifespan cycle. | fix: in
  `stop_scheduler()` add `global _http; if _http: await _http.aclose(); _http =
  None` (make `stop_scheduler` async, or schedule the close on the loop),
  mirroring the singleton cleanup done for the engine elsewhere.

- [cleanup] worker/cron.py:90 — `_scheduler.shutdown(wait=False)` does not wait
  for an in-flight digest job, so a deploy at ~07:00 could interrupt a running
  email send mid-flight. Likely intentional (a 300 s digest shouldn't hang
  shutdown), but the trade-off is undocumented. | fix: keep `wait=False` and add
  a one-line comment stating the deliberate choice, or pass a short bounded wait.

- [cleanup] memory/retrieval.py:37-42 — `_WealthPositionContract` and
  `_IncomePositionContract` are empty placeholder classes that are never
  referenced; dead code that reads as unfinished scaffolding. | fix: delete both,
  or replace with real `TypedDict`s if the structural contract is wanted.

- [cleanup] memory/retrieval.py:53,59 — `full_wealth`/`full_income` are annotated
  `VaultWealthPosition`/`VaultIncomePosition` but the `except` branches assign
  plain dicts (`_EMPTY_WEALTH`/`_EMPTY_INCOME`), a silent annotation mismatch a
  type checker on the vault TypedDicts would flag. | fix: type the empties as the
  same TypedDict (or annotate the vars `dict`) so the fallback path type-checks.

- [cleanup] memory/retrieval.py:137 — `"memory_summary": None, # populated by
  Issue 9` is an inline forward-reference/TODO for an unshipped feature. | fix:
  fine to keep as a documented placeholder, but drop the issue-number comment
  (stale once Issue 9 lands) or track it in issues.md instead of source.

- [cleanup] db/indexes — the retrieval "active decisions" query
  (memory/retrieval.py:71-76) filters `status == 'active'` ordered by
  `decided_at DESC LIMIT 10` but there is **no index** on `decisions(status,
  decided_at)` (patterns.detected_at and messages.conversation_id are both
  indexed). Negligible at single-user Road-A volume, but a composite index is the
  senior-polish move for the showcase. | fix: add
  `ix_decisions_status_decided_at` on `("status", "decided_at")` in a migration.

- [cleanup] scenarios/engine.py:24-87 — `_time_to_target` (~64 lines) mixes the
  computation, three branches of user-facing message formatting, and the
  reasoning-trace string build in one function. Readable but does more than one
  thing. | fix: extract the message/reasoning formatting into a small
  `_format_time_to_target_result()` helper; keep `_time_to_target` to
  dispatch + assemble the ScenarioOutput.

## Positives (portfolio polish — no action)
- scenarios/models.py:34-49 — `field_validator` correctly rejects negative money
  (`current_amount`, `monthly_contribution`, `current_monthly_income`) → 422, and
  deliberately allows negative `delta_monthly` (an income cut), with a comment
  explaining why. Matches the roadmap requirement exactly.
- scenarios/engine.py — projection loop is hard-bounded by `_MAX_MONTHS = 600`
  (section 2 bounded-work: clean). Decimal money math is correct end-to-end:
  `annual_pct / 100 / 12` and `balance * (1 + r) + contribution` stay Decimal
  (int divisors/operands don't coerce to float); floats appear only in cosmetic
  reasoning strings.
- memory/models.py — every sensitive column is encrypted
  (`summary_encrypted`, `content_encrypted`, `EncryptedJSON` vault-refs);
  plaintext columns (`role`, `kind`, `severity`, `cited_principle`) carry no PII.
- memory/retrieval.py — fixed set of bounded queries (each `.limit()`ed), no N+1;
  loggers emit only exception messages, never account figures; dollar aggregates
  rounded to nearest $100 (ROUND_CEILING) before entering the LLM prompt.
- digest.py:140,145 — DB session via `async with` context manager (guaranteed
  close); blocking `smtplib` send correctly offloaded via `asyncio.to_thread`,
  and the whole job is wrapped in `asyncio.wait_for(...300s)` so a hung SMTP/LLM
  call can't wedge the scheduler.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | 1 finding (_http never closed); DB sessions & digest timeout clean |
| 2 Concurrency & scale | ok — bounded loops, indexed access paths, no N+1, blocking SMTP offloaded |
| 3 Security & compliance | ok — sensitive memory columns encrypted, no PII/token in logs; single-user Road A |
| 4 Domain correctness | ok — negative-money 422 validator + Decimal money math correct; disclaimer flagged when return>0 |
| 5 LLM SDK | n/a (retrieval builds the prompt block but issues no LLM call in this slice) |
| 6 Cleanliness & typing | 4 cleanups (dead classes, annotation mismatch, stale TODO, long fn) |
| 7 Error handling / API | n/a (router surface owned by another module) |
| 8 Config & paths | ok — healthcheck_ping_url & digest_recipient documented in .env.example, typed settings |

## Module verdict
NEEDS-WORK — no blockers; two SEV2s worth closing (digest dedup guard + closing
the leaked httpx client on shutdown) plus small cleanups, on an otherwise
senior-quality slice (bounded math, correct Decimal handling, encrypted memory,
good index coverage).
