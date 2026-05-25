"""HTMX UI for the vault — ergonomic manual entry (the primary input mode).

Manual entry is the primary data path for v1 (Plaid deferred, see
docs/DECISIONS.md "Free-first data ingestion strategy"), so the forms are
tuned for a <30 min/month steady-state workload on a 10+ account vault:

  - duplicate-last-entry / prior-period defaults: `GET .../form?from_last=1`
    prefills every field from the most recent row
  - keyboard-only flow: first field autofocuses; submit resets and refocuses
    so the next row can be typed without touching the mouse
  - batch entry: side-income sessions post many rows in one request

These fragment endpoints render small HTML snippets that HTMX swaps in. CRUD
behavior (encryption, audit, computed fields) is reused from vault/crud.py via
the same EntitySpec registry the JSON API uses. Delete reuses the JSON
endpoint (`hx-delete` to `/{prefix}/{id}`).
"""
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from auth import User, get_current_user
from db import get_session
from vault import crud
from routers.vault import ENTITIES

router = APIRouter(prefix="/ui", tags=["vault-ui"])

_STATIC = Path(__file__).resolve().parent.parent / "static" / "vault.html"
_SPEC_BY_PREFIX = {spec.prefix: spec for spec in ENTITIES}


@dataclass
class UIField:
    name: str
    label: str
    kind: str = "text"  # text | number | int | date | datetime | bool | select
    required: bool = False
    options: list[str] = dc_field(default_factory=list)


@dataclass
class UIEntity:
    prefix: str
    title: str
    fields: list[UIField]
    # optional post-parse hook (e.g. gather expense_* inputs into expenses_jsonb)
    assemble: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _assemble_side_income(data: dict[str, Any]) -> dict[str, Any]:
    expenses = {
        key[4:]: value
        for key, value in list(data.items())
        if key.startswith("exp_") and value is not None
    }
    for key in list(data):
        if key.startswith("exp_"):
            data.pop(key)
    if expenses:
        data["expenses_jsonb"] = expenses
    return data


UI_ENTITIES: dict[str, UIEntity] = {
    "cards": UIEntity("cards", "Credit / Debit Cards", [
        UIField("account_id", "Account ID", "int", required=True),
        UIField("issuer", "Issuer", "text", required=True),
        UIField("network", "Network", "text", required=True),
        UIField("last4", "Last 4", "text"),
        UIField("credit_limit", "Credit limit", "number"),
        UIField("statement_day", "Statement day", "int"),
        UIField("due_day", "Due day", "int"),
        UIField("current_cycle_spend", "Cycle spend", "number"),
        UIField("autopay", "Autopay", "bool"),
        UIField("status", "Status", "text"),
    ]),
    "retirement_accounts": UIEntity("retirement_accounts", "Retirement Accounts", [
        UIField("kind", "Kind", "select", required=True,
                options=["roth_ira", "traditional_ira", "401k", "solo_401k", "sep_ira", "hsa"]),
        UIField("institution", "Institution", "text", required=True),
        UIField("ytd_contribution", "YTD contribution", "number"),
        UIField("balance", "Balance", "number"),
        UIField("notes", "Notes", "text"),
    ]),
    "career_position": UIEntity("career_position", "Career Position", [
        UIField("current_role", "Current role", "text", required=True),
        UIField("current_employer", "Current employer", "text", required=True),
        UIField("current_comp_total", "Current comp", "number"),
        UIField("target_role", "Target role", "text"),
        UIField("target_comp_total", "Target comp", "number"),
        UIField("target_date", "Target date", "date"),
        UIField("notes", "Notes", "text"),
    ]),
    "side_income_economics": UIEntity("side_income_economics", "Side-Income Economics", [
        UIField("income_stream_id", "Income stream ID", "int", required=True),
        UIField("period_start", "Period start", "date", required=True),
        UIField("period_end", "Period end", "date", required=True),
        UIField("gross", "Gross", "number"),
        UIField("hours_worked", "Hours worked", "number"),
        UIField("exp_gas", "Expense: gas", "number"),
        UIField("exp_food", "Expense: food", "number"),
        UIField("exp_other", "Expense: other", "number"),
    ], assemble=_assemble_side_income),
    "tax_deductions_1099": UIEntity("tax_deductions_1099", "1099 Deductions", [
        UIField("tax_year", "Tax year", "int", required=True),
        UIField("category", "Category", "select", required=True,
                options=["mileage", "home_office", "equipment", "education", "other"]),
        UIField("amount", "Amount", "number"),
        UIField("evidence_note", "Evidence note", "text"),
    ]),
}


def _get_ui(prefix: str) -> UIEntity:
    ui = UI_ENTITIES.get(prefix)
    if ui is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown form")
    return ui


def _convert(kind: str, raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return None
    try:
        if kind == "number":
            return Decimal(raw)
        if kind == "int":
            return int(raw)
        if kind == "date":
            return date.fromisoformat(raw)
        if kind == "datetime":
            return datetime.fromisoformat(raw)
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid value: {raw!r}"
        ) from exc
    return raw


def _parse_form(ui: UIEntity, form: dict[str, str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for field in ui.fields:
        if field.kind == "bool":
            parsed[field.name] = field.name in form
            continue
        if field.name in form:
            value = _convert(field.kind, form[field.name])
            if value is not None:
                parsed[field.name] = value
    if ui.assemble:
        parsed = ui.assemble(parsed)
    return parsed


def _input_html(field: UIField, value: Any = None, suffix: str = "", autofocus: bool = False) -> str:
    name = f"{field.name}{suffix}"
    val = "" if value is None else escape(str(value))
    af = " autofocus" if autofocus else ""
    req = " required" if field.required else ""
    label = escape(field.label)
    if field.kind == "bool":
        checked = " checked" if value else ""
        return (
            f'<label class="fld"><input type="checkbox" name="{name}"{checked}> {label}</label>'
        )
    if field.kind == "select":
        opts = "".join(
            f'<option value="{escape(o)}"{" selected" if str(value) == o else ""}>{escape(o)}</option>'
            for o in field.options
        )
        return f'<label class="fld">{label}<select name="{name}"{req}{af}>{opts}</select></label>'
    input_type = {"number": "number", "int": "number", "date": "date",
                  "datetime": "datetime-local"}.get(field.kind, "text")
    step = ' step="0.01"' if field.kind == "number" else ""
    return (
        f'<label class="fld">{label}'
        f'<input type="{input_type}"{step} name="{name}" value="{val}"{req}{af}></label>'
    )


def _render_form(ui: UIEntity, prefill: dict[str, Any] | None = None) -> str:
    prefill = prefill or {}
    inputs = "".join(
        _input_html(f, prefill.get(f.name), autofocus=(i == 0))
        for i, f in enumerate(ui.fields)
    )
    return (
        f'<form id="{ui.prefix}-form" class="vform" '
        f'hx-post="/ui/{ui.prefix}" hx-target="#{ui.prefix}-list" hx-swap="afterbegin" '
        f'hx-on::after-request="if(event.detail.successful){{this.reset();'
        f'this.querySelector(\'input,select\').focus();}}">'
        f'{inputs}'
        f'<div class="actions">'
        f'<button type="submit">Save</button> '
        f'<button type="button" hx-get="/ui/{ui.prefix}/form?from_last=1" '
        f'hx-target="#{ui.prefix}-form" hx-swap="outerHTML">Duplicate last</button>'
        f'</div></form>'
    )


def _render_row(prefix: str, out_data: dict[str, Any]) -> str:
    entity_id = out_data.get("id")
    cells = " · ".join(
        f"{escape(k)}: {escape(str(v))}"
        for k, v in out_data.items()
        if k != "id" and v is not None
    )
    return (
        f'<li class="row" id="{prefix}-{entity_id}">'
        f'<span class="rid">#{entity_id}</span> {cells} '
        f'<button class="del" hx-delete="/{prefix}/{entity_id}" '
        f'hx-target="#{prefix}-{entity_id}" hx-swap="delete" '
        f'hx-confirm="Delete #{entity_id}?">delete</button>'
        f'</li>'
    )


def _out_dump(spec, obj) -> dict[str, Any]:
    return spec.out_schema.model_validate(obj).model_dump()


@router.get("/vault", response_class=HTMLResponse)
async def vault_page() -> FileResponse:
    return FileResponse(_STATIC)


@router.get("/{prefix}/form", response_class=HTMLResponse)
async def get_form(
    prefix: str,
    from_last: int = 0,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    ui = _get_ui(prefix)
    prefill: dict[str, Any] = {}
    if from_last:
        spec = _SPEC_BY_PREFIX[prefix]
        last = await crud.get_last_entity(session, spec.model)
        if last is not None:
            data = _out_dump(spec, last)
            prefill = {f.name: data.get(f.name) for f in ui.fields}
            if ui.assemble and isinstance(data.get("expenses_jsonb"), dict):
                for key, value in data["expenses_jsonb"].items():
                    prefill[f"exp_{key}"] = value
    return HTMLResponse(_render_form(ui, prefill))


@router.get("/{prefix}/list", response_class=HTMLResponse)
async def get_list(
    prefix: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    _get_ui(prefix)
    spec = _SPEC_BY_PREFIX[prefix]
    rows = await crud.list_entities(session, spec.model)
    html = "".join(_render_row(prefix, _out_dump(spec, row)) for row in rows)
    return HTMLResponse(html)


@router.get("/{prefix}/section", response_class=HTMLResponse)
async def get_section(
    prefix: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    ui = _get_ui(prefix)
    spec = _SPEC_BY_PREFIX[prefix]
    rows = await crud.list_entities(session, spec.model)
    list_html = "".join(_render_row(prefix, _out_dump(spec, row)) for row in rows)
    body = (
        f"<h2>{escape(ui.title)}</h2>"
        f"{_render_form(ui)}"
        f'<ul id="{prefix}-list" class="rows">{list_html}</ul>'
    )
    return HTMLResponse(body)


@router.post("/{prefix}", response_class=HTMLResponse)
async def create_from_form(
    prefix: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    ui = _get_ui(prefix)
    spec = _SPEC_BY_PREFIX[prefix]
    form = dict(await request.form())
    parsed = _parse_form(ui, form)
    try:
        payload = spec.in_schema.model_validate(parsed)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors(include_url=False)
        ) from exc
    obj = await crud.create_entity(
        session, spec.model, payload.model_dump(exclude_unset=True),
        actor=user.username, entity_type=spec.entity_type, compute=spec.compute,
    )
    return HTMLResponse(_render_row(prefix, _out_dump(spec, obj)))


@router.post("/side_income_economics/batch", response_class=HTMLResponse)
async def create_side_income_batch(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Batch-create side-income rows: fields are suffixed `-0`, `-1`, ... per row."""
    ui = _get_ui("side_income_economics")
    spec = _SPEC_BY_PREFIX["side_income_economics"]
    form = dict(await request.form())
    indexes = sorted({key.rsplit("-", 1)[1] for key in form if key.rsplit("-", 1)[-1].isdigit()})
    if not indexes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No rows")
    rows_html: list[str] = []
    for idx in indexes:
        row_form = {
            key.rsplit("-", 1)[0]: value
            for key, value in form.items()
            if key.endswith(f"-{idx}")
        }
        parsed = _parse_form(ui, row_form)
        try:
            payload = spec.in_schema.model_validate(parsed)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(include_url=False),
            ) from exc
        obj = await crud.create_entity(
            session, spec.model, payload.model_dump(exclude_unset=True),
            actor=user.username, entity_type=spec.entity_type, compute=spec.compute,
        )
        rows_html.append(_render_row("side_income_economics", _out_dump(spec, obj)))
    return HTMLResponse("".join(rows_html))
