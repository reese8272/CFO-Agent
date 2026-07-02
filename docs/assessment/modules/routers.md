# routers — assessed 2026-07-02

Slice: `routers/` — chat.py, digest.py, holdings.py, imports.py, intake.py, memory.py,
scenarios.py, vault.py, wealth.py. HTTP API surface (rubric §7 applies fully).

## Findings

### Rate limiting (LLM / expensive routes unguarded)
- [SEV1] routers/chat.py:31 — `POST /chat` invokes the LangGraph agent (multiple Anthropic
  calls) with **no `@limiter.limit`**. `rate_limit.limiter` exists and is wired
  (`app.state.limiter`), but is only applied in auth.py (login/register). An authenticated
  client can drive unbounded LLM spend / DoS the agent | fix: add
  `@limiter.limit("10/minute")` and take `request: Request` as the first param (slowapi needs
  it).
- [SEV1] routers/intake.py:678 — `POST /intake/interview` calls Anthropic every turn with no
  rate limit | fix: `@limiter.limit("20/minute")` + `request: Request`.
- [SEV1] routers/intake.py:711 — `POST /intake/extract` calls Anthropic (max_tokens=4096, full
  transcript) with no rate limit | fix: `@limiter.limit("6/minute")` + `request: Request`.
- [SEV2] routers/digest.py:21 — `POST /digest/run-now` triggers a full digest generation
  (LLM + SMTP send) with no rate limit; can be spammed to send repeated emails | fix:
  `@limiter.limit("3/hour")`.

### Async hygiene — blocking calls on the event loop
- [SEV1] routers/holdings.py:95 — `fetch_price(ticker)` (sync `yfinance` + `requests.get`,
  10s timeouts) called directly inside `async def refresh_all_prices`, in a loop over every
  ticker. Each call blocks the whole event loop; a portfolio of N tickers stalls all
  concurrent requests for up to N×timeout seconds | fix: wrap each call in
  `await asyncio.to_thread(fetch_price, ticker)` (vault.py:512 already does this correctly for
  the RentCast call — mirror it).
- [SEV1] routers/holdings.py:118 — same blocking `fetch_price(obj.ticker)` inside
  `async def refresh_single_price` | fix: `await asyncio.to_thread(fetch_price, obj.ticker)`.

### Bounded work — unbounded list fetches
- [SEV2] routers/vault.py — all 17 `GET` list endpoints (accounts, cards, income-streams,
  expenses, debts, assets, real-estate, business-income, retirement-accounts, goals,
  career-position, career-history, comp-benchmarks, side-income-economics, tax-deductions,
  negotiation-milestones, net-worth-snapshots) call `crud.list_*` which issue
  `select(Model).order_by(Model.id)` with **no LIMIT** (verified `vault/crud.py:108`
  `list_accounts` and siblings) → unbounded `fetchall`, unbounded HTMX row render. Also
  holdings.py:48/142, imports.py:76, intake.py:440 (`/intake/archive`), wealth.py:47
  (`net_worth_snapshots`, full table). memory.py is the correct pattern (`.limit(20/50)`) |
  fix: add a capped `limit: int = Query(100, le=500)` param threaded into each `crud.list_*`,
  or a hard `.limit(500)` default in the crud layer.

### Security — per-tenant isolation (scale axis D / pre-GA)
- [SEV1] routers/vault.py, holdings.py, memory.py, imports.py, intake.py, wealth.py — **no
  query is scoped to the authenticated user**. Verified `vault/models.py` and `memory/models.py`
  have no `user_id`/`owner_id` column at all; `crud.list_accounts` etc. select globally, and
  `get_account(session, id)` fetches any row by PK. Correct for documented single-user v1
  (THREAT_MODEL §Out-of-Scope), but this is the load-bearing pre-GA gate: the moment a 2nd
  user exists, every vault/holdings/memory/import read and every mutation is a cross-tenant
  leak | fix (pre-GA): add `user_id` FK to every tenant-scoped table + `.where(Model.user_id
  == user.id)` on every crud query + a regression test asserting user B cannot read user A's
  row. Track as the blocker in the Pre-GA checklist before any invite.

### LLM SDK usage (intake.py — direct Anthropic calls)
- [SEV1] routers/intake.py:695 & :724 — **token usage not logged** after either Anthropic
  call. CLAUDE.md mandates "token usage logged after every call"; `response.usage` is
  discarded | fix: `logger.info("intake tokens in=%s out=%s", r.usage.input_tokens,
  r.usage.output_tokens)` after each `.create`.
- [SEV1] routers/intake.py:695 — **no prompt caching** despite a large static system prompt
  (`_INTERVIEW_SYSTEM`) reused every turn, and :724 sends the large static `_EXTRACT_TOOL`
  schema uncached. CLAUDE.md: "prompt caching mandatory" | fix: add
  `"cache_control": {"type": "ephemeral"}` to the trailing system block (and to the tool /
  static prefix on extract).
- [SEV2] routers/intake.py:660 — model id hardcoded `_MODEL = "claude-sonnet-4-6"`, not
  sourced from typed settings (rubric §5); the id is also non-standard and may not resolve
  (needs-runtime-confirmation) | fix: read from `get_settings().anthropic_model` (as the agent
  layer does) and verify the id against the current Anthropic model list.

### Error handling & API surface (§7)
- [SEV2] routers/digest.py:30 — `detail=f"Digest send failed: {exc}"` leaks the raw exception
  (SMTP host/error internals) to the client | fix: return a fixed
  `detail="Digest send failed"` and keep `logger.error(... exc)` server-side only.
- [SEV2] routers/wealth.py:27,35,41,47 — endpoints return bare `dict` with **no response
  Pydantic model** (rubric §7 requires a validated model on every response); CONTRACTS.md §3
  even specifies the shapes | fix: declare `response_model` with the frozen shapes
  (`{"allocation": WealthPosition, "income": IncomePosition}`, etc.). Same gap on
  intake.py:167 `/status`, :440 `/archive`, and the holdings.py:82 refresh-prices dict.
- [SEV2] routers/imports.py:26 — `parse_csv/parse_ofx(content)` on arbitrary uploaded bytes is
  unguarded; a malformed file raises and surfaces as an unhandled 500 (default handler). Also
  no file-size cap on `await file.read()` (unbounded memory) | fix: wrap parse in
  `try/except ValueError -> HTTPException(422, "could not parse file")`; enforce a max upload
  size.
- [cleanup] routers/holdings.py:70, vault.py:138 (all DELETEs) — 404 detail strings are safe;
  status codes correct across the module. No stack-trace leakage found elsewhere (chat.py:56
  correctly returns generic "Agent error").

### Cleanliness & typing (§6)
- [SEV2] routers/intake.py:190 — `submit_intake` is ~220 lines doing profile upsert + 11
  entity-population blocks + snapshot + archive (KISS/SRP) | fix: extract per-section helpers
  (`_populate_debts(session, body)`, etc.) or move to a `vault/intake_service.py`.
- [cleanup] routers/vault.py — every entity duplicates its HTMX field-tuple in both the
  create and list handler (DRY, 17×2) | fix: hoist one `_FIELDS: dict[str, list[tuple]]`
  module constant keyed by entity_type.
- [cleanup] routers/imports.py:11 — imports private `_apply_mappings_raw` from
  `integrations.csv_import` (reaching past the module's public API) | fix: expose a public
  wrapper.
- [cleanup] routers/holdings.py:5, imports.py:5 — unused `select` import in holdings.py;
  `datetime`/`Decimal` imports in intake.py used only in nested scopes | fix: linter cleanup.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | ok — sessions via `Depends(get_session)` context; Anthropic/HTTP clients are singletons (`get_anthropic`) |
| 2 Concurrency & scale | 2 SEV1 (blocking `fetch_price` in async) + 1 SEV2 (unbounded list fetches) |
| 3 Security & compliance | 1 SEV1 (no per-tenant scoping / pre-GA gate); parameterized SQL only; no balances/tokens logged in this slice |
| 4 Domain correctness | n/a — disclaimer surfaced on wealth.py + real-estate refresh; recommendation-commit logic lives in agent/, not routers |
| 5 LLM SDK | 2 SEV1 (no token logging, no prompt caching) + 1 SEV2 (hardcoded/non-standard model id) in intake.py |
| 6 Cleanliness & typing | 1 SEV2 (220-line submit_intake) + DRY/import cleanups |
| 7 Error handling / API | 3 SEV2 (leaked digest error, missing response models, unguarded upload parse) |
| 8 Config & paths | model id belongs in settings (folded into §5); no path issues — all imports absolute |

## Module verdict
NEEDS-WORK — no BLOCKER for documented single-user v1, but LLM routes (`/chat`,
`/intake/interview|extract`, `/digest/run-now`) ship with no rate limit, holdings price-refresh
blocks the event loop, and intake's direct Anthropic calls skip token logging + prompt caching;
per-tenant scoping is the pre-GA blocker to close before any second user.
