# routers — assessed 2026-07-03

Slice: `routers/{vault,holdings,imports,chat,wealth,memory,scenarios,digest,intake}.py` (+ `__init__.py`).
Single-user "Road A"; multi-tenant explicitly deferred (CLAUDE.md), so absence of `WHERE user_id=` on list/CRUD queries is a *recorded design assumption*, not a leak — noted, not flagged as BLOCKER.

## Findings

- [SEV2] routers/imports.py:66-84 — per-row N+1 in the import loop: one `SELECT ... WHERE import_hash = h`
  plus a `flush()` and a `write_audit_log` INSERT for **every** row. A 10 MB statement is thousands of
  round-trips inside one request → slow, lock-heavy, and effectively a self-inflicted DoS on the DB even
  single-user | fix: pre-load existing hashes for the account in one query
  (`SELECT import_hash FROM transactions WHERE account_id = :id`) into a set, filter in memory,
  `session.add_all(new_txns)`, and write a single summary audit row per batch instead of one per txn.

- [SEV2] routers/imports.py:23-30 — `account_id` arrives as an unvalidated query param; a non-existent id is
  never checked, so `ImportBatch(account_id=...)` fails only at COMMIT with a DB `IntegrityError` → unhandled
  500 (generic, but a 500 for a client-input error is wrong) | fix:
  `if not await crud.get_account(session, account_id): raise HTTPException(404, "account not found")`
  before parsing, returning 404/422 for bad input.

- [SEV2] routers/holdings.py:93-112 (+ vault/crud.py:873) — `list_distinct_tickers` is misnamed: it returns
  **every** holdings row, so batch refresh fetches the same ticker's price N times (redundant external
  yfinance calls) and reports duplicate tickers in the `updated` list; `total` counts rows, not tickers |
  fix: `select(distinct(Holdings.ticker))`, fetch each price once, then update all rows for that ticker;
  rename accordingly.

- [SEV2] routers/vault.py:486 (`refresh-values`) & routers/holdings.py:86 (`refresh-prices`) — the two
  endpoints that fan out to paid/external APIs (RentCast, yfinance) carry **no** `@limiter.limit`, while the
  cheaper LLM endpoints (chat 10/min, extract 6/min) do. A tight client loop burns RentCast quota / rate-caps
  yfinance | fix: add `@limiter.limit("6/hour")` (add `request: Request` param) to both refresh endpoints.

- [cleanup] routers/vault.py:48, holdings.py:32, wealth.py:26, chat.py:15, digest.py:14, memory.py:17,
  scenarios.py:12, imports.py:18 — `CurrentUser = Annotated[str, Depends(get_current_user)]` but
  `get_current_user` returns `User` (auth.py:140), and vault/holdings do `user.username` on it. The type says
  `str.username`, which a checker should reject; intake.py:39 already gets this right | fix: `from auth import User`
  and use `Annotated[User, Depends(get_current_user)]` everywhere.

- [cleanup] routers/vault.py:55-1097 — every one of the ~18 entities duplicates its HTMX field-tuple list
  verbatim between its `create_*` (row render) and `list_*` (`_htmx_list`) handlers (DRY). A senior reviewer
  reads this file and sees copy-paste | fix: define one `_FIELDS: dict[str, list[tuple[str,str]]]` (or a small
  per-entity spec) and reference it in both handlers.

- [cleanup] routers/imports.py:13 — router imports the private `_apply_mappings_raw` across a module boundary
  (integrations.csv_import) — leaky layering | fix: expose a public `apply_mappings(description, mappings)` in
  csv_import and import that.

- [cleanup] routers/chat.py:60-66 — `ChatResponse(recommendation=result["recommendation"], …)` runs *outside*
  the try/except, so a graph state missing a key throws `KeyError` → raw 500 (the try only wraps `ainvoke`) |
  fix: build the response inside the guarded block, or validate the terminal state keys before indexing.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | ok — sessions via `get_session` dep (context-managed), commits on every mutation path, `get_anthropic`/`limiter` are module singletons |
| 2 Concurrency & scale | 2 findings (imports N+1; holdings redundant per-row fetch). Blocking calls (yfinance/RentCast) correctly offloaded via `asyncio.to_thread` + `wait_for` timeout |
| 3 Security & compliance | ok for Road A — parameterized ORM only; HTML escaped in `_entity_row_html` (XSS-safe); no balance/token/PII in log lines (verified). Absence of per-user WHERE is the recorded single-user assumption, not a defect |
| 4 Domain correctness | ok — refresh-values embeds mandatory appraisal disclaimer; mileage constant sourced from `agent.principles.MILEAGE_RATE_2026`; chat passes through `disclaimer`/`principle`/`vision_stamp` |
| 5 LLM SDK | ok — intake interview/extract use ephemeral prompt caching, log input/output/cache-read tokens, model from `get_settings()`, forced `tool_choice`, explicit `max_tokens`. Minor: `content[0].text` assumes first block is text |
| 6 Cleanliness & typing | 4 cleanups — wrong `str` CurrentUser annotation, HTMX field-list duplication, private cross-module import, chat KeyError-outside-try |
| 7 Error handling / API | 1 finding (imports unvalidated account_id → 500). Otherwise strong: response_model on every JSON endpoint, correct 201/204/404/422/502/503, error messages generic (digest 502, graph 500 hide internals) |
| 8 Config & paths | ok — RentCast key gated with 503 when absent; all config via `get_settings()`; no hardcoded paths |

## Module verdict
NEEDS-WORK — no blockers; the API surface, status codes, and error hygiene are solid, but the imports N+1 (+ unvalidated account_id), the mislabeled ticker refresh, unthrottled external-API refresh endpoints, and the `str`-typed CurrentUser + HTMX duplication are the fixes a senior reviewer would expect before calling it portfolio-clean.
