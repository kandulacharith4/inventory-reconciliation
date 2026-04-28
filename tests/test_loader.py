from pathlib import Path
import textwrap

from src.loader import load_snapshot, normalize_sku, normalize_quantity


def test_normalize_sku_variants():
    assert normalize_sku("SKU-001") == "SKU-001"
    assert normalize_sku("sku-001") == "SKU-001"
    assert normalize_sku("SKU001") == "SKU-001"
    assert normalize_sku(" SKU-1 ") == "SKU-001"


def test_normalize_quantity_handles_floats_and_blanks():
    assert normalize_quantity("70") == (70, None)
    assert normalize_quantity("70.0")[0] == 70
    assert normalize_quantity("70.00")[0] == 70
    assert normalize_quantity("70.5")[0] == 70
    assert normalize_quantity("")[1] is not None
    assert normalize_quantity("abc")[1] is not None


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return p


def test_load_snapshot_detects_duplicate_sku(tmp_path):
    p = _write(tmp_path, "s.csv", """
        sku,name,quantity,location,last_counted
        SKU-001,Widget,10,A,2024-01-01
        SKU-001,Widget,5,A,2024-01-01
    """)
    items, issues = load_snapshot(p, "s")
    assert len(items) == 1
    assert any(i.issue_type == "duplicate_sku" for i in issues)


def test_load_snapshot_alias_columns(tmp_path):
    p = _write(tmp_path, "s.csv", """
        sku,product_name,qty,warehouse,updated_at
        SKU-001,Widget,10,A,2024-01-01
    """)
    items, _ = load_snapshot(p, "s")
    assert items[0].name == "Widget"
    assert items[0].quantity == 10


def test_load_snapshot_flags_negative_quantity(tmp_path):
    p = _write(tmp_path, "s.csv", """
        sku,name,quantity,location,last_counted
        SKU-001,Widget,-5,A,2024-01-01
    """)
    _, issues = load_snapshot(p, "s")
    assert any(i.issue_type == "negative_quantity" for i in issues)


def test_load_snapshot_flags_bad_date(tmp_path):
    p = _write(tmp_path, "s.csv", """
        sku,name,quantity,location,last_counted
        SKU-001,Widget,10,A,01/15/2024
    """)
    _, issues = load_snapshot(p, "s")
    assert any(i.issue_type == "date_format" for i in issues)


def test_load_snapshot_flags_whitespace_in_name(tmp_path):
    p = _write(tmp_path, "s.csv", """
        sku,name,quantity,location,last_counted
        SKU-001, Widget ,10,A,2024-01-01
    """)
    items, issues = load_snapshot(p, "s")
    assert items[0].name == "Widget"
    assert any(i.issue_type == "whitespace_in_name" for i in issues)
