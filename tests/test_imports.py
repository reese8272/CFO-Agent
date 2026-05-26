"""CSV/OFX import unit tests — no live DB required."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from integrations.csv_import import compute_hash, parse_csv, _apply_mappings_raw


def test_parse_csv_happy_path():
    csv_bytes = b"date,amount,description\n2026-01-15,-42.50,AMAZON.COM\n2026-01-16,1500.00,PAYROLL\n"
    rows = parse_csv(csv_bytes)
    assert len(rows) == 2
    assert rows[0].amount == Decimal("-42.50")
    assert rows[0].description == "AMAZON.COM"
    assert rows[0].occurred_at.year == 2026


def test_parse_csv_skips_bad_rows():
    csv_bytes = b"date,amount,description\nNOT-A-DATE,10.00,valid\n2026-03-01,25.00,good\n"
    rows = parse_csv(csv_bytes)
    assert len(rows) == 1
    assert rows[0].description == "good"


def test_compute_hash_deterministic():
    dt = datetime(2026, 1, 15, tzinfo=timezone.utc)
    h1 = compute_hash(1, dt, Decimal("42.50"), "AMAZON")
    h2 = compute_hash(1, dt, Decimal("42.50"), "AMAZON")
    assert h1 == h2
    assert len(h1) == 64


def test_compute_hash_differs_on_amount():
    dt = datetime(2026, 1, 15, tzinfo=timezone.utc)
    h1 = compute_hash(1, dt, Decimal("42.50"), "AMAZON")
    h2 = compute_hash(1, dt, Decimal("42.51"), "AMAZON")
    assert h1 != h2


def test_parse_ofx_import_error(monkeypatch):
    import integrations.csv_import as m
    monkeypatch.setattr(m, "_import_ofxtools", lambda: (_ for _ in ()).throw(ImportError()))
    import pytest
    with pytest.raises(RuntimeError):
        m.parse_ofx(b"garbage")


def test_category_mapping_applied():
    mapping = MagicMock()
    mapping.pattern = "amazon"
    mapping.category = "Shopping"
    result = _apply_mappings_raw("AMAZON.COM purchase", [mapping])
    assert result == "Shopping"
