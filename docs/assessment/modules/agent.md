# agent — re-assessed 2026-07-02 (post-remediation)

Branch `hardening/phase-7-finish-line` @ `9ef25a5`. Re-verification of the seven
findings raised in the original 2026-07-02 assessment (`docs/assessment/REPORT.md`),
by reading the current code. Evidence is `file:line`.

## Findings

1. **[BLOCKER] Synthesizer dropped disclaimer when final LLM returned
   `requires_disclaimer=false` — FIXED.**
   `agent/nodes/synthesizer.py:86-89` now OR-folds the final flag with the
   proposals' flags:
   `needs_disclaimer = bool(result.get("requires_disclaimer")) or any(p.get("requires_disclaimer") for p in state.get("proposals", []))`,
   then `disclaimer = get_disclaimer() if needs_disclaimer else None`. Matches the
   expected fix exactly.

2. **[SEV1] `_route_from_analyzer` returned a single node (only one specialist
   fired) — FIXED.**
   `agent/graph.py:93-104` now returns `list[str]` — de-duped
   `[_ROUTE_TO_NODE[r] for r in routes ...]`, falling back to `["coach"]` when no
   specialist matches. Conditional edge map (`graph.py:127-137`) wires all four
   specialists + coach for true parallel fan-out. Signature is `-> list[str]`.

3. **[SEV1] `proposals` used `operator.add`, so Coach duplicated proposals —
   FIXED.**
   `agent/state.py:70` declares
   `proposals: Annotated[list[NodeProposal], merge_proposals]`; the reducer
   `merge_proposals` (`state.py:37-49`) keeps one entry per `node` (replace-by-node),
   so parallel specialists accumulate but Coach's re-emitted nodes replace rather
   than append. Coach returns replacement proposals at `coach.py:144`.

4. **[SEV2] Coach fragile `next(... tool_use)` under MAX_TOKENS=512 could 500 —
   FIXED.**
   `agent/nodes/coach.py:116` uses guarded `next((b for b in ... ), None)`;
   `coach.py:117-123` falls back to passing the raw proposals through (with a
   warning log of `stop_reason`) instead of raising. `MAX_TOKENS` raised to 2048
   (`coach.py:18`, comment notes 512 truncated multi-specialist turns).

5. **[SEV2] tax_optimizer hardcoded 22% bracket — FIXED.**
   `agent/principles.py:21` defines year-stamped
   `ASSUMED_FED_MARGINAL_BRACKET_2026: float = 0.22`;
   `agent/nodes/tax_optimizer.py:14` imports it and `tax_optimizer.py:69-71` uses
   it in the quarterly-estimate calc. No literal `0.22` remains in the node.

6. **[cleanup] leverage_score unclamped; legacy anthropic-beta prompt-caching
   header — FIXED (one stale docstring remains).**
   leverage_score is clamped to 0–1 in every emitter:
   `strategist.py:91`, `career.py:80`, `tax_optimizer.py:99`, `coach.py:130`
   (`max(0.0, min(1.0, float(...)))`); `income_optimizer.py` bounds via
   `min(gap_pct, Decimal("1.0"))` and fixed 0.3/0.4 fallbacks. No functional
   `anthropic-beta` / `extra_headers` / `default_headers` remains in `clients.py`
   or any node — caching is via native `cache_control` blocks. NOTE: a stale
   descriptive docstring still reads `anthropic-beta prompt-caching-2024-07-31` at
   `agent/prompts.py:1`; cosmetic only, not load-bearing.

7. **[SEV1, DEFERRED] Per-tenant scoping (no `user_id` filter) — STILL DEFERRED
   (not a regression).**
   `agent/graph.py:33` retrieval is still hardcoded `user_id="owner"` and
   `persist_node` (`graph.py:37-82`) writes Conversation/Message/Decision rows with
   no tenant column. This is the documented Road-A single-user deferral, unchanged
   from the original assessment — deferred, not regressed.

## Module verdict
All six in-scope findings FIXED (one cosmetic stale docstring at prompts.py:1); the single SEV1 per-tenant scoping item remains a documented Road-B deferral — agent module is production-ready for single-user scope.
