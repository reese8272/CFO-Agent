"""Pydantic input/output models for the scenario engine."""
from __future__ import annotations
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, field_validator


class ScenarioKind(str, Enum):
    time_to_target = "time_to_target"
    income_change = "income_change"


class ScenarioInput(BaseModel):
    kind: ScenarioKind

    # --- time_to_target params ---
    current_amount: Decimal | None = None        # current savings/investment balance
    monthly_contribution: Decimal | None = None  # added each month
    annual_return_pct: Decimal | None = None     # e.g. 7.0 for 7%; use 0 for cash
    target_amount: Decimal | None = None         # goal balance to reach

    # --- income_change params ---
    current_monthly_income: Decimal | None = None   # baseline total monthly income
    delta_monthly: Decimal | None = None            # change per month (negative = cut)

    @field_validator("annual_return_pct")
    @classmethod
    def _return_pct_range(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (Decimal("0") <= v <= Decimal("50")):
            raise ValueError("annual_return_pct must be between 0 and 50")
        return v


class ScenarioOutput(BaseModel):
    kind: ScenarioKind
    result: dict
    reasoning_trace: str
    assumed_constants: dict
    requires_disclaimer: bool
    disclaimer: str | None = None
