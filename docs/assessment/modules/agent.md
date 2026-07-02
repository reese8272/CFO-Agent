# agent — assessed 2026-07-02

Slice: `agent/graph.py`, `state.py`, `prompts.py`, `principles.py`, `principles_investing.py`,
`principles_real_estate.py`, `principles_saas.py`, and all nodes in `agent/nodes/`.

## Findings

- [BLOCKER] agent/nodes/synthesizer.py:83 — the mandatory disclaimer is set **only** from the
  Synthesizer LLM's own `requires_disclaimer` output; it ignores the `requires_disclaimer` flag
  on the contributing proposals. `tax_optimizer` always sets `requires_disclaimer=True`
  (tax_optimizer.py:99) and `alert` sets it True for Roth/deduction alerts, yet if the final LLM
  call returns `requires_disclaimer=false`, the disclaimer is silently dropped on tax/investment
  output. This violates the frozen hard rule in CONTRACTS.md §2 ("`disclaimer` is non-null
  whenever any contributing proposal set `requires_disclaimer`") and the CLAUDE.md mandatory-
  disclaimer domain rule. | fix: compute `needs = result.get("requires_disclaimer") or
  any(p["requires_disclaimer"] for p in state.get("proposals", []))` and set
  `disclaimer = get_disclaimer() if needs else None`. Add the structural test the disclaimer.py
  docstring already promises (Issue 7).

- [SEV1] agent/nodes/coach.py:136 + agent/state.py:56 — Coach intends to **replace** the
  proposal list ("replace existing ones (Coach is the authority on final cite)") but
  `proposals` uses `Annotated[list[NodeProposal], operator.add]`, so returning
  `{"proposals": new_proposals}` **appends**. After Strategist appends P1, Coach appends its
  enriched copy, leaving the Synthesizer duplicate proposals (raw + enriched) and inflating the
  set the Synthesizer sorts/picks from. | fix: Coach must not re-emit via the additive channel.
  Either (a) have Coach write enriched citations to a separate non-additive state key the
  Synthesizer reads, or (b) give `proposals` a custom reducer that replaces entries with the same
  `node`. Add a test asserting `len(proposals)` after Coach equals the specialist count.

- [SEV1] agent/graph.py:85-97 — `_route_from_analyzer` returns a **single** node name, so despite
  `routes` being a list and `turn_kind` supporting `"both"`, only ONE specialist
  (strategist | career | income_optimizer | tax_optimizer | coach) ever fires per turn. The
  `operator.add` reducer, the parallel fan-out in CONTRACTS.md §1/§2, and multi-topic turns are
  all dead — a "what should I do next?" turn that routes to allocation+income runs Strategist only,
  never Career/Income-Optimizer. | fix: use `graph.add_conditional_edges` with a list return (or
  fan out with parallel edges gated on `routes`) so every routed specialist runs and each appends
  its own proposal, then converge on Coach. Add an eval asserting a "both" turn yields ≥2 proposals.

- [SEV1] agent/nodes/tracker.py:38-49, agent/nodes/alert.py:110-212, agent/graph.py:33 — no
  per-tenant scoping. Retrieval hardcodes `user_id="owner"`, and the Tracker/Alert queries
  (`select(NetWorthSnapshot)`, `select(Goal)`, `select(RetirementAccount).where(kind=='roth_ira')`,
  `select(TaxDeduction1099)`, `select(NegotiationMilestone)`, `select(CareerPosition)`) have **no
  `WHERE user_id = ?`**. Harmless while single-user, but the moment a second user exists (the stated
  goal is public/portfolio-grade) every one of these is a cross-tenant read — this becomes a
  BLOCKER at that point. | fix: thread `user_id` through `tracker_node`/`alert_node` from state and
  add `.where(Model.user_id == user_id)` to every query; add a two-tenant regression test asserting
  tenant B's snapshots/goals/milestones never surface for tenant A. Track under the CLAUDE.md
  pre-GA multi-tenant checklist.

- [SEV2] agent/nodes/{analyzer,strategist,coach,career,tax_optimizer,synthesizer}.py:14-19 —
  model ids are hardcoded module constants (`MODEL = "claude-sonnet-4-6"` / `"claude-haiku-4-5-20251001"`)
  repeated across six nodes; `config.py` has no `anthropic_model` field (rubric §5: model id must
  come from typed settings). The ids themselves are valid current models (Sonnet 4.6, Haiku 4.5) —
  no stale/invalid id — but they cannot be changed without editing six files. | fix: add
  `anthropic_model_fast` / `anthropic_model_smart` to `Settings` (config.py) with defaults, document
  in `.env.example`, and read them in the nodes.

- [SEV2] agent/nodes/tax_optimizer.py:68 — `estimated_quarterly = income_1099_ytd * (SE_TAX_RATE + 0.22) / 4`
  hardcodes a 22% income-tax bracket for every user and is not year-stamped or sourced from
  `agent/principles.py`. Quarterly estimate is wrong for anyone outside the 22% bracket and the
  magic `0.22` is undocumented. | fix: derive the marginal bracket from the user's income (or make
  it an explicit, year-stamped constant in `principles.py`) and cite it "for 2026…" like the other
  constants.

- [SEV2] agent/nodes/coach.py:95-101 — the full `PRINCIPLES` registry (16 cite strings) is
  concatenated into the **volatile user message** on every Coach call, so it is never cached, unlike
  the static `_SYSTEM` block. Re-sends the same ~1–2k tokens uncached each turn. | fix: move the
  registry text into a second cached system block (`cache_control: ephemeral`) alongside `_SYSTEM`.

- [SEV2] agent/nodes/coach.py:104-115 — Coach forces an array-valued tool output
  (`enriched_proposals`) under `MAX_TOKENS=512`; if the response truncates (`stop_reason=max_tokens`)
  the `tool_use` input is incomplete and `next(b ... if b.type == "tool_use")` yields malformed
  input or raises `StopIteration` → unhandled 500. Same fragile `next(...)` pattern in every LLM
  node. | fix: raise Coach `MAX_TOKENS` (array output scales with proposal count), and guard the
  extraction: `tool_block = next((b for b in response.content if b.type == "tool_use"), None)` with
  an explicit fallback proposal if `None`.

- [cleanup] agent/nodes/strategist.py:12, coach.py:12, tax_optimizer.py:11-14 — unused imports:
  `get_principle` (strategist, coach) and `ROTH_IRA_LIMIT_2026` (tax_optimizer). | fix: remove.

- [cleanup] agent/nodes/*.py — `extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}` is
  the legacy beta header; prompt caching is GA and the header is unnecessary (harmless but stale). |
  fix: drop the header; keep the `cache_control` blocks.

- [cleanup] agent/nodes/{strategist,coach,career,tax_optimizer}.py — LLM-returned `leverage_score`
  is cast to float but never clamped to 0.0–1.0 (the contract range); `income_optimizer` clamps,
  the LLM nodes do not, so the Synthesizer could sort on an out-of-range score. | fix:
  `max(0.0, min(1.0, float(r["leverage_score"])))`.

## Rubric coverage
| Category | Status |
|---|---|
| 1 Resource lifecycle | ok — DB via `async with get_sessionmaker()()`; Anthropic/Redis are module singletons in clients.py |
| 2 Concurrency & scale | ok-ish — no blocking calls in async nodes; but tenant queries unindexed-by-user (see SEV1 isolation), and NetWorthSnapshot limited to 12 (bounded) |
| 3 Security & compliance | 2 findings — BLOCKER disclaimer drop; SEV1 missing per-tenant scoping. No PII/balance in log lines (verified). |
| 4 Domain correctness | 2 findings — disclaimer (BLOCKER); tax 22%-bracket assumption (SEV2). Principle citations + year-stamped constants otherwise correct. |
| 5 LLM SDK | 1 finding — prompt caching present + static/volatile split ok; token usage logged every call; model id hardcoded not from settings (SEV2); legacy beta header (cleanup). |
| 6 Cleanliness & typing | 3 cleanups — unused imports, stale header, unclamped score. Signatures typed. |
| 7 Error handling / API | n/a (no router/handler in slice) — note fragile `next(...)` tool extraction (SEV2 under Coach). |
| 8 Config & paths | ok — settings via pydantic-settings fail-fast; add `anthropic_model` + `0.22`/thresholds to `.env.example` per SEV2s. |

## Module verdict
has BLOCKER — the mandatory disclaimer can be dropped on tax/investment output because the
Synthesizer ignores proposals' `requires_disclaimer`; additionally the Coach additive-reducer
duplication and single-specialist routing defeat the parallel node design, and no query is
per-tenant scoped ahead of the stated public launch.
