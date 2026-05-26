from __future__ import annotations
import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


@dataclass
class ParsedRow:
    occurred_at: datetime
    amount: Decimal
    description: str
    raw: dict


def compute_hash(account_id: int, occurred_at: datetime, amount: Decimal, description: str) -> str:
    key = f"{account_id}|{occurred_at.isoformat()}|{amount}|{description}"
    return hashlib.sha256(key.encode()).hexdigest()


def parse_csv(content: bytes) -> list[ParsedRow]:
    text = content.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows: list[ParsedRow] = []
    for raw in reader:
        row = {k.lower().strip(): v.strip() for k, v in raw.items() if k}
        date_str = (
            row.get("date")
            or row.get("posted date")
            or row.get("transaction date")
            or ""
        )
        amount_str = row.get("amount") or row.get("debit") or row.get("credit") or "0"
        desc = row.get("description") or row.get("memo") or row.get("payee") or ""
        try:
            dt = datetime.fromisoformat(date_str.replace("/", "-"))
        except ValueError:
            continue
        try:
            amount = Decimal(amount_str.replace(",", "").replace("$", ""))
        except InvalidOperation:
            continue
        rows.append(
            ParsedRow(
                occurred_at=dt.replace(tzinfo=timezone.utc),
                amount=amount,
                description=desc,
                raw=raw,
            )
        )
    return rows


def _import_ofxtools() -> type:
    """Import and return OFXTree class. Isolated for testability."""
    from ofxtools.Parser import OFXTree  # noqa: PLC0415
    return OFXTree


def parse_ofx(content: bytes) -> list[ParsedRow]:
    try:
        OFXTree = _import_ofxtools()
    except ImportError:
        raise RuntimeError("ofxtools not installed")
    parser = OFXTree()
    parser.parse(io.BytesIO(content))
    ofx = parser.convert()
    rows: list[ParsedRow] = []
    stmts = []
    if ofx.bankmsgsrsv1:
        stmts.extend(ofx.bankmsgsrsv1)
    if ofx.creditcardmsgsrsv1:
        stmts.extend(ofx.creditcardmsgsrsv1)
    for stmt in stmts:
        tl = getattr(stmt, "banktranlist", None) or getattr(stmt, "cctranlist", None)
        if tl is None:
            continue
        for txn in tl:
            dt = txn.dtposted
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            rows.append(
                ParsedRow(
                    occurred_at=dt,
                    amount=Decimal(str(txn.trnamt)),
                    description=txn.name or txn.memo or "",
                    raw={"fitid": txn.fitid},
                )
            )
    return rows


def _apply_mappings_raw(description: str, mappings: list) -> str | None:
    """Apply category mappings to a transaction description.

    Each mapping object must expose `.pattern` and `.category` attributes.
    Returns the first matching category, or None if no match.
    """
    desc_lower = description.lower()
    for m in mappings:
        if m.pattern.lower() in desc_lower:
            return m.category
    return None
