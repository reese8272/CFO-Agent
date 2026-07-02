"""Agent routing fan-out + proposal-reducer correctness (Phase 6)."""
from agent.graph import _route_from_analyzer
from agent.state import merge_proposals


def _p(node: str, score: float = 0.5, rationale: str = "raw") -> dict:
    return {
        "node": node, "move": f"move-{node}", "principle": "x",
        "leverage_score": score, "rationale": rationale, "requires_disclaimer": False,
    }


# --- routing: every matched specialist fans out (not just the top priority) ---

def test_route_returns_all_matched_specialists():
    got = _route_from_analyzer({"routes": ["allocation", "income"]})
    assert set(got) == {"strategist", "income_optimizer"}
    assert len(got) == 2  # both fire — the old code returned only "strategist"


def test_route_dedupes_and_preserves_order():
    got = _route_from_analyzer({"routes": ["tax", "tax", "career"]})
    assert got == ["tax_optimizer", "career"]


def test_route_falls_back_to_coach_when_no_specialist():
    assert _route_from_analyzer({"routes": []}) == ["coach"]
    assert _route_from_analyzer({"routes": ["general"]}) == ["coach"]


# --- reducer: fan-in accumulates distinct nodes; Coach replaces (no dup) ---

def test_merge_accumulates_distinct_nodes():
    """Parallel specialists each emit a distinct node → they accumulate."""
    merged = merge_proposals([_p("strategist")], [_p("income_optimizer")])
    assert {p["node"] for p in merged} == {"strategist", "income_optimizer"}


def test_merge_replaces_same_node_no_duplication():
    """Coach re-emits the same nodes enriched → replaces, not duplicates
    (the operator.add bug produced raw + enriched)."""
    raw = [_p("strategist", rationale="raw"), _p("tax_optimizer", rationale="raw")]
    enriched = [
        _p("strategist", rationale="enriched"),
        _p("tax_optimizer", rationale="enriched"),
    ]
    merged = merge_proposals(raw, enriched)
    assert len(merged) == 2  # not 4
    assert all(p["rationale"] == "enriched" for p in merged)
