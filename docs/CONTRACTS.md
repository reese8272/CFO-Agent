# Frozen Interfaces — Contract Freeze (2026-05-25)

**Purpose**: This file freezes the interfaces that downstream issues depend on, so the
agent nodes, endpoints, and integrations can be built **in parallel** without any builder
having to guess another's output. If a builder needs to deviate from a contract here, they
**stop and amend this file first** (with a `docs/DECISIONS.md` entry if it's architectural) —
they do not invent a divergent shape.

This is the anti-hallucination lever for the hybrid build plan: serial through the
foundation (`4 → 4b → 5 → 6 → 7`), parallel at the leaves (`8`, `8b`, `10`, `11`, `4c`)
once the contracts below are frozen.

> **Disclaimer**: This tool is for financial education and personal organization. It is not a
> licensed financial advisor. For tax strategy, real estate transactions, and investment
> decisions, consult a licensed professional.

---

## 1. Agent state contract — `agent/state.py` (frozen for Issue 7+)

The single LangGraph state object. Every node reads and writes **only** the keys assigned to
it in §2. `proposals` uses a **replace-by-`node` reducer** (`merge_proposals`) so parallel
specialists accumulate one entry per node while the Coach replaces (rather than duplicates)
by node. *(Amended 2026-07-02, Phase 6 — was `operator.add`; see `docs/DECISIONS.md`.)*

```python
import operator
from typing import Annotated, Literal, NotRequired, TypedDict

AllocationStep = Literal[1, 2, 3, 4, 5, 6]
IncomeStep = Literal[1, 2, 3, 4, 5]
TurnKind = Literal["allocation", "income", "both", "general"]

# One of the frozen keys in §4. Nodes MUST cite from this set; never invent a name.
PrincipleKey = str


class WealthPosition(TypedDict):
    step: AllocationStep
    step_name: str          # e.g. "Tax-Advantaged"
    rationale: str          # which gate is unmet, in one sentence
    next_move: str          # the concrete next action on this track


class IncomePosition(TypedDict):
    step: IncomeStep
    step_name: str
    rationale: str
    next_move: str


class NodeProposal(TypedDict):
    node: str               # "strategist" | "career" | "income_optimizer" | "tax_optimizer" | "alert"
    move: str               # the single proposed move (imperative, specific)
    principle: PrincipleKey # a key from §4
    leverage_score: float   # 0.0–1.0; the Synthesizer picks the highest across all proposals
    rationale: str
    requires_disclaimer: bool  # True if the move touches tax / legal / investment specifics


class AgentState(TypedDict):
    # --- inputs (set by the chat router before invoke) ---
    user_message: str
    conversation_id: int | None

    # --- Retrieval node writes ---
    vault_snapshot: dict             # redacted aggregates only (see §3 Retrieval)
    wealth_position: WealthPosition
    income_position: IncomePosition
    active_decisions: list[dict]     # [{id, summary, principle, status, expires_at}]
    recent_patterns: list[dict]      # [{kind, severity, summary, detected_at}]
    memory_summary: str | None

    # --- Analyzer node writes ---
    turn_kind: TurnKind
    routes: list[str]                # subset of node names to fire conditionally

    # --- conditional nodes contribute one entry per node (parallel-safe via reducer) ---
    proposals: Annotated[list[NodeProposal], merge_proposals]

    # --- Tracker node writes ---
    trajectory_note: str             # pace vs goals + target curve, one short paragraph
    net_worth_pace: NotRequired[dict]  # {current, target_at_now, delta, on_pace: bool}

    # --- Synthesizer node writes (terminal, the ONE committed move) ---
    recommendation: str
    reasoning: str
    principle: PrincipleKey          # the single cited principle for the chosen move
    disclaimer: str | None           # set iff any fired proposal had requires_disclaimer
    vision_stamp: str                # one clause: how this advances the 10-yr net-worth vision

    # --- token accounting (logged after every Anthropic call per CLAUDE.md) ---
    tokens_in: int
    tokens_out: int
```

**Graph topology** (matches `docs/SOT.md` Agent Architecture):
`Retrieval → Analyzer → [conditional: Strategist | Career | Income-Optimizer | Tax-Optimizer | Coach | Alert] → Tracker → Synthesizer → Persist`.

---

## 2. Node I/O contracts (frozen for Issues 7, 8, 8b, 10)

Each node is a pure function `(AgentState) -> partial AgentState`. It reads only its declared
inputs and writes only its declared outputs. This is what lets each node be built by a
separate parallel agent.

| Node | File | Fires when | Reads | Writes |
|---|---|---|---|---|
| Retrieval | `agent/nodes/` (Issue 6) | always (entry) | `user_message`, DB | `vault_snapshot`, `wealth_position`, `income_position`, `active_decisions`, `recent_patterns`, `memory_summary` |
| Analyzer | `analyzer.py` | always | full state | `turn_kind`, `routes` |
| Strategist | `strategist.py` | `"allocation"` in routes | `wealth_position`, `vault_snapshot`, `active_decisions` | appends one `NodeProposal` (allocation move) |
| Career | `career.py` | `"income"`/career in routes | `income_position`, `career_position`, `comp_benchmarks` (in snapshot) | appends one `NodeProposal` |
| Income-Optimizer | `income_optimizer.py` | income/streams in routes | `income_position`, side-income economics in snapshot | appends one `NodeProposal` (cut/scale) |
| Tax-Optimizer | `tax_optimizer.py` | tax in routes | `tax_deductions_1099`, 1099 income in snapshot, `agent/principles.py` | appends one `NodeProposal`; `requires_disclaimer=True` |
| Coach | `coach.py` | always (post-proposals) | `proposals`, arena principle libs | enriches each proposal's `principle` + one-sentence why |
| Tracker | `tracker.py` | always | `wealth_position`, goals + `net_worth_snapshots` in snapshot | `trajectory_note`, `net_worth_pace` |
| Alert | `alert.py` | thresholds breached | `recent_patterns`, snapshot deltas | appends `NodeProposal` (proactive) |
| Synthesizer | `synthesizer.py` | always (terminal) | `proposals` (+ scores), `trajectory_note` | `recommendation`, `reasoning`, `principle`, `disclaimer`, `vision_stamp` — commits to ONE |
| Persist | `agent/graph.py` (Issue 7/9) | always (after Synthesizer) | terminal state | DB rows: messages, decisions, patterns, audit |

**Hard rules** (enforced by eval harness + structural tests):
- Synthesizer commits to exactly one move; it does not enumerate options unless `user_message` explicitly asks for options.
- `disclaimer` is non-null whenever any contributing proposal set `requires_disclaimer`.
- Every proposal's `principle` is a key from §4.

---

## 3. Position + endpoint contracts (frozen for Issue 5)

**Computation functions** (deterministic, no LLM):

```python
# vault/wealth_position.py
async def compute_wealth_position(session: AsyncSession) -> WealthPosition: ...

# vault/income_position.py
async def compute_income_position(session: AsyncSession) -> IncomePosition: ...
```

Step logic is the 6-step allocation sequence and 5-step income sequence in
`docs/WEALTH_PRINCIPLES.md` — the position is the lowest step whose gate is unmet.

**Endpoints** (`routers/wealth.py`, all behind `get_current_user`):

| Method + path | Response shape |
|---|---|
| `GET /wealth/position` | `{"allocation": WealthPosition, "income": IncomePosition}` |
| `GET /wealth/trajectory` | `{"goals": [{id, title, current, target, deadline, pct, on_pace}], ...}` |
| `GET /wealth/net_worth_trajectory` | `{"history": [{as_of, net_worth, assets, liabilities}], "target_curve": [{as_of, target}], "on_pace": bool}` |

**Retrieval `vault_snapshot` contract** (redacted aggregates only, per THREAT_MODEL §4): rounded
totals by category, last-4s never full numbers, no SSN/full-address/DOB. Exact dollar precision
only where arithmetic requires it.

---

## 4. Frozen principle-key registry (frozen for Issues 6, 8, 8b)

Nodes cite a principle by one of these stable keys (slugs of the named principles in
`docs/WEALTH_PRINCIPLES.md`). Adding a key requires updating both that file and this list.

```
assets_over_liabilities        emergency_fund_first        debt_avalanche
time_in_market                 tax_arbitrage               employer_match_capture
solo_401k_for_1099             lifestyle_creep_avoidance   career_income_as_wealth_lever
real_estate_leverage           business_income_compounding job_switch_comp_arbitrage
deduction_discipline_1099      side_income_hourly_truth    quarterly_estimated_tax
comp_negotiation_anchor_high
```

Arena-specific keys (real estate / SaaS / investing) are added when those libraries land
(Issue 8). Year-versioned tax constants are **not** principles — they live in
`agent/principles.py`, stamped with the year, and the agent says "for <year>…" when citing one.

---

## 5. Chat endpoint contract (frozen for Issue 7)

```
POST /chat   (behind get_current_user)
  body:     {"message": str, "conversation_id": int | null}
  response: {"recommendation": str, "reasoning": str, "principle": str,
             "disclaimer": str | null, "vision_stamp": str, "conversation_id": int}
```

This is the public projection of the Synthesizer's terminal `AgentState`.

---

## 6. Build plan this freeze enables

- **Serial spine** (one Check→Approve→Build→Review each): `4 → 4b → 5 → 6 → 7`. Each genuinely
  feeds the next; building them in order keeps the contracts above honest as they solidify.
- **Parallel leaves** (fan out after Issue 7 lands and §1/§2 are proven against a real run):
  - Agent nodes `8` (Analyzer/Strategist/Coach) and `8b` (Career/Income-Optimizer/Tax-Optimizer) — one agent per node, each against §2.
  - `10` (Tracker/Alert), `11` (scenario engine, depends only on §3), `4c` (CSV import, depends only on 4b).
- Shared files that parallel agents must treat as append-only merge points: `main.py` (router
  mounts), `requirements.txt`, `agent/graph.py` (node registration), `agent/state.py` (frozen — do not edit without amending this doc).
