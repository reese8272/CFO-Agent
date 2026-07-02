from __future__ import annotations
import csv
import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"]
# Bound in-memory accumulation on a crafted/oversized upload. A statement with
# more rows than this is rejected rather than parsed into an unbounded list.
MAX_ROWS = 50_000


@dataclass
class ParsedRow:
    occurred_at: datetime
    amount: Decimal
    description: str
    raw: dict


def _parse_date(date_str: str) -> datetime | None:
    """Try each format in _DATE_FORMATS; return None if none match."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _parse_amount(row: dict) -> Decimal | None:
    """Resolve amount from debit/credit columns or a signed amount column.

    When separate debit/credit columns exist, computes credit - debit so that
    credits are positive and debits are negative (standard bank convention).
    Handles parenthetical negatives like (123.45) → -123.45.
    """
    def _clean(s: str) -> str:
        s = s.strip().replace(",", "").replace("$", "")
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        return s

    debit_str = row.get("debit", "").strip()
    credit_str = row.get("credit", "").strip()

    if debit_str or credit_str:
        try:
            debit = Decimal(_clean(debit_str)) if debit_str else Decimal("0")
            credit = Decimal(_clean(credit_str)) if credit_str else Decimal("0")
            return credit - debit
        except InvalidOperation:
            return None

    amount_str = row.get("amount", "").strip()
    if not amount_str:
        return Decimal("0")
    try:
        return Decimal(_clean(amount_str))
    except InvalidOperation:
        return None


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
        desc = row.get("description") or row.get("memo") or row.get("payee") or ""
        dt = _parse_date(date_str)
        if dt is None:
            logger.debug("csv_import: skipping row with unparseable date %r", date_str)
            continue
        amount = _parse_amount(row)
        if amount is None:
            continue
        if len(rows) >= MAX_ROWS:
            raise ValueError(f"file exceeds the {MAX_ROWS}-row import limit")
        rows.append(
            ParsedRow(
                occurred_at=dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt,
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
            if len(rows) >= MAX_ROWS:
                raise ValueError(f"file exceeds the {MAX_ROWS}-row import limit")
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
