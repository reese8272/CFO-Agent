# routers — re-assessed 2026-07-02 (post-remediation)

Branch: `hardening/phase-7-finish-line`. Each original 2026-07-02 finding re-verified against
current source. Evidence is `file:line`. See git history for the pre-remediation version of
this file.

## Verified findings

| # | Sev | Finding | Status | Evidence |
|---|-----|---------|--------|----------|
| 1 | SEV1 | `/chat`, `/intake/interview`, `/intake/extract`, `/digest/run-now` had NO `@limiter.limit` | **FIXED** | `chat.py:33` `@limiter.limit("10/minute")` + `chat.py:34` `request: Request`; `intake.py:677` `@limiter.limit("20/minute")` + `intake.py:679` `request: Request`; `intake.py:721` `@limiter.limit("6/minute")` + `intake.py:723` `request: Request`; `digest.py:23` `@limiter.limit("3/hour")` + `digest.py:24` `request: Request` |
| 2 | SEV1 | `holdings.py` refresh called blocking `fetch_price` on the event loop | **FIXED** | Imports `fetch_price_async` (`asyncio.to_thread` wrapper) at `holdings.py:18`; awaited in batch loop `holdings.py:92` and single refresh `holdings.py:115`. No blocking `fetch_price` remains |
| 3 | SEV1 | `intake.py` direct Anthropic calls: no token logging, no prompt caching | **FIXED** | interview: `cache_control ephemeral` on system `intake.py:701`, usage logged (in/out/cache_read) `intake.py:711-716`; extract: `cache_control` on system `intake.py:741` and tool `intake.py:744`, usage logged `intake.py:747-752` |
| 4 | SEV2 | `intake.py` hardcoded model id | **FIXED** | `intake.py:696` and `intake.py:736` both use `get_settings().anthropic_model_smart`; no literal model string present |
| 5 | SEV2 | `imports.py` unbounded upload parse, unhandled 500 | **FIXED** | `MAX_UPLOAD_BYTES` `imports.py:20`; 413 on `file.size` pre-check and post-read `len(content)` `imports.py:31-35`; parse via `asyncio.to_thread` `imports.py:41,44`; parse failure → 422 `imports.py:46-50` |
| 6 | SEV2 | `digest.py` leaked raw exception in 502 detail | **FIXED** | Generic `detail="Digest send failed"` `digest.py:33`; raw `exc` only logged server-side `digest.py:32` |
| 7 | SEV2 | 17 vault `GET` list endpoints unbounded (no limit cap) — deferred to Phase 4b | **DEFERRED (still open)** | All list handlers call `crud.list_*(session)` with no limit/offset: `vault.py:110,169,226,283,338,394,450,553,610,667,724,781,838,896,953,1009,1066`. Also `holdings.py:47,141`, `intake.py:447` (`/archive`), `wealth.py:52`. Pagination not yet added — matches Phase 4b deferral |
| 8 | SEV2 | `wealth.py`/`intake` bare-dict responses (no `response_model`) — deferred to Phase 5b | **DEFERRED (still open)** | `wealth.py:27,35,41,47` all `-> dict`, no `response_model`; `intake.py:168` (`/status`) and `intake.py:720` (`/extract` uses loose `response_model=dict`). Unchanged — matches Phase 5b deferral |
| 9 | SEV1 | per-tenant scoping — documented single-user deferral (Road B) | **DEFERRED (documented)** | Queries unscoped by user, e.g. `intake.py:173,202,421` (`select(UserProfile)` / `select(FinancialSnapshot)` with no user predicate), `vault.py` `crud.list_*` calls, `memory.py:61,68,78,98`. Correct for documented single-user v1; pre-GA blocker per Road B |

## Module verdict

**PASS (post-remediation).** All six actionable SEV1/SEV2 findings (1–6) are FIXED with concrete
evidence in current source, and none regressed to OPEN. The three remaining items (7 Phase-4b
pagination, 8 Phase-5b response models, 9 Road-B per-tenant scoping) are the previously-agreed
deferrals and remain correctly open/deferred — none is a new or reopened defect.

- FIXED: 6 (findings 1–6)
- OPEN: 0
- DEFERRED: 3 (findings 7, 8, 9)

Top remaining item: **#7 — 17 unbounded vault `GET` list endpoints (no limit/offset cap)**; close
in Phase 4b by threading a bounded `limit`/`offset` through the `crud.list_*` layer.
