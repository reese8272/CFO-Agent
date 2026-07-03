# agent — assessed 2026-07-03

Scope: `agent/graph.py`, `agent/state.py`, `agent/principles.py`, `agent/prompts.py`,
`agent/principles_{investing,real_estate,saas}.py`, `agent/nodes/*.py`
(analyzer, strategist, career, income_optimizer, tax_optimizer, coach, tracker, alert,
synthesizer). Fresh Layer-1 pass; supersedes the 2026-07-02 remediation-verification note.

## Findings

- [SEV2] nodes/tax_optimizer.py:103 — token usage is **not** logged after this LLM call
  (its `logger.info` records only `principle` + `score`; every other LLM node logs
  `tokens_in`/`tokens_out`). Violates rubric §5 and CLAUDE.md "token usage logged after
  every call." | fix: add `response.usage.input_tokens` / `.output_tokens` to the log line,
  matching strategist.py:96.

- [SEV2] nodes/{analyzer,coach,strategist,career,tax_optimizer}.py — only the Synthesizer
  returns `tokens_in`/`tokens_out` into `AgentState` (synthesizer.py:99-100); the other 1–5
  Anthropic calls per turn are logged but never accumulated into state, so `persist_node`
  (graph.py:63-67) writes **only the Synthesizer's tokens** to the `Message` row. Per-turn
  cost/usage is undercounted by up to ~5 calls (Analyzer + fanned-out specialists + Coach).
  | fix: have each LLM node return `{"tokens_in": ..., "tokens_out": ...}` and add an
  `Annotated[int, operator.add]` reducer for those keys in state.py so they sum across nodes;
  persist the total.

- [SEV2] nodes/analyzer.py:75, strategist.py:84, career.py:73, tax_optimizer.py:92,
  synthesizer.py:69 — bare `next(b for b in response.content if b.type == "tool_use")` raises
  `StopIteration` (→ uncaught 500) if the model truncates at `max_tokens` before completing a
  `tool_use` block. Coach already guards exactly this (coach.py:116, `next(..., None)` +
  fallback) and documents the risk — these five nodes don't. Synthesizer at `max_tokens=1024`
  with a 7-field structured tool is the most exposed. | fix: use
  `next((b for b in response.content if b.type == "tool_use"), None)` and handle
  `None`/`stop_reason == "max_tokens"` with a safe fallback (as coach does) or a handled 502.

- [SEV2] nodes/coach.py:44 — the Coach tool's `principle` field is an unconstrained
  `{"type": "string"}` (no `enum`), unlike Strategist/Career/Tax which pin it to registry
  keys. Coach is "the authority on final cite" and *replaces* proposals (coach.py:143), so it
  can emit a `principle` outside the frozen §4 registry — violating CONTRACTS §2 hard rule
  "every proposal's `principle` is a key from §4." Compounded: the arena keys the Coach is
  told to cite (`house_hacking`, `mrr_arr`, `three_fund`, … in
  principles_{real_estate,saas,investing}.py) are **not** in `PRINCIPLES` / §4, so
  `get_principle()` would `KeyError` on them. | fix: add `"enum": get_all_keys()` to the Coach
  tool's `principle`, and register arena keys in §4 / principles.py before allowing the Coach
  to cite them.

- [cleanup] nodes/analyzer.py:69, strategist.py:78, career.py:67, tax_optimizer.py:87,
  coach.py:108 — `cache_control: ephemeral` is set on system prompts far below the minimum
  cacheable prefix (~1024 tokens Sonnet / ~2048 Haiku). These ~100–300-token blocks will never
  cache — cargo-cult caching. Only the Synthesizer's `CFO_SYSTEM_PROMPT` + profile block
  (synthesizer.py:50-61) is large enough to benefit. | fix: drop `cache_control` from the small
  system prompts, or comment that it's a deliberate no-op.

- [cleanup] nodes/strategist.py, career.py, tax_optimizer.py — near-identical
  "single-proposal LLM node" boilerplate (build context → `messages.create` with forced tool →
  extract tool_use → clamp `leverage_score` 0–1 → build `NodeProposal` → log). DRY. | fix:
  extract a `run_proposal_node(system, tool, context, node_name)` helper in
  `agent/nodes/_llm.py`; this also fixes the StopIteration and token-accounting findings in one
  place.

- [cleanup] agent/state.py:77 — `financial_snapshot: dict | None` is declared in AgentState but
  no node reads or writes it (Retrieval writes `vault_snapshot`); appears dead and diverges
  from the frozen CONTRACTS §1 shape. | fix: remove it or wire it.

- [cleanup] agent/prompts.py:1 — module docstring still references the legacy
  `anthropic-beta prompt-caching-2024-07-31` header; caching is now native `cache_control`.
  Cosmetic/stale. | fix: update the docstring.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | ok — every DB touch (retrieval/tracker/alert/persist) uses `async with get_sessionmaker()()`; Anthropic + Redis are module-level singletons with bounded timeout/retries (clients.py) |
| 2 Concurrency & scale | ok — all LLM/DB work is `await`ed, no blocking calls in async; income_optimizer is a pure sync node; alert runs 4 sequential bounded queries — no N+1 loop |
| 3 Security & compliance | ok — nodes log only principle/score/tokens/latency, no balances or account numbers; `vault_snapshot` is redacted aggregates per CONTRACTS §3; disclaimer OR-folded from ALL proposals in synthesizer.py:86-89 (never trusts the final LLM flag alone) |
| 4 Domain correctness | 1 finding — Coach `principle` unconstrained + arena keys unregistered (§4 violation). Otherwise strong: year-stamped constants in principles.py, tax node forces `requires_disclaimer=True`, leverage_score clamped 0–1 everywhere, list-fanout + `merge_proposals` replace-by-node work as specified |
| 5 LLM SDK | 2 findings — tax_optimizer missing token log; token accounting to state/DB captures only the Synthesizer. Positives: forced `tool_choice` structured output, explicit `max_tokens` per node (Coach bumped to 2048 with a documented truncation guard), model ids from typed settings (config.anthropic_model_smart/fast), Synthesizer caching splits static system + profile |
| 6 Cleanliness & typing | 3 cleanups — no-op caching, DRY boilerplate, dead `financial_snapshot` key + stale docstring; signatures otherwise typed |
| 7 Error handling / API | 1 finding — bare `next()` tool_use extraction (StopIteration → 500) in 5 nodes; these are graph nodes, so HTTP status mapping lives in the router |
| 8 Config & paths | ok — model ids, timeout, retries from typed `Settings`; no hardcoded model strings in nodes; no filesystem paths in this module |

## Module verdict
NEEDS-WORK — no blockers; architecture (frozen state contract, list-fanout routing,
replace-by-node reducer, disclaimer aggregation) is clean and portfolio-grade, but LLM-hygiene
gaps (incomplete token accounting, one node not logging tokens, unguarded tool_use extraction in
5 nodes, and an unconstrained Coach `principle` that can escape the frozen registry) should be
fixed before it headlines the showcase.
