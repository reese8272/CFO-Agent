"""Scenario modeling endpoint — POST /scenarios/run."""
from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from auth import User, get_current_user
from scenarios.models import ScenarioInput, ScenarioOutput
from scenarios.engine import run_scenario

router = APIRouter(prefix="/scenarios", tags=["scenarios"])
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/run", response_model=ScenarioOutput)
def scenarios_run(body: ScenarioInput, _user: CurrentUser) -> ScenarioOutput:
    try:
        return run_scenario(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
