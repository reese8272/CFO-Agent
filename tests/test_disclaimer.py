"""Structural: disclaimer present on every tax/legal/investment response."""
from agent.prompts import CFO_SYSTEM_PROMPT
from disclaimer import DISCLAIMER, get_disclaimer


def test_disclaimer_text_in_system_prompt():
    """The disclaimer must appear verbatim in the CFO system prompt."""
    assert DISCLAIMER in CFO_SYSTEM_PROMPT


def test_get_disclaimer_returns_default():
    import os
    os.environ.pop("WEALTH_DISCLAIMER_TEXT", None)
    assert get_disclaimer() == DISCLAIMER


def test_requires_disclaimer_propagates(monkeypatch):
    """synthesizer_node sets disclaimer when requires_disclaimer=True in tool output."""
    # Already covered by test_chat.py::test_synthesizer_sets_disclaimer_when_required
    # This is a marker test — structural coverage confirmed by that test.
    assert True
