"""Tests for the JSON and CSV output layer."""
import csv
import json
from pathlib import Path

import pytest

from src.models import (
    InventoryItem, QuantityChange, NameChange, LocationChange,
    QualityIssue, ReconciliationReport,
)
from src.reporters import write_json, write_csv, write_quality_csv


# ── helpers ────────────────────────────────────────────────────────────────

def _item(sku, name="Widget", qty=10, location="Warehouse A"):
    return InventoryItem(sku=sku, name=name, quantity=qty,
                         location=location, last_counted="2024-01-15")


def _sample_report() -> ReconciliationReport:
    return ReconciliationReport(
        unchanged=[_item("SKU-006")],
        quantity_changed=[
            QuantityChange(sku="SKU-001", name="Widget A", location="Warehouse A",
                           old_quantity=150, new_quantity=145),
        ],
        name_changed=[
            NameChange(sku="SKU-045", old_name="Multimeter Pro",
                       new_name="Multimeter Professional"),
        ],
        location_changed=[
            LocationChange(sku="SKU-010", old_location="Warehouse A",
                           new_location="Warehouse B"),
        ],
        removed=[_item("SKU-025", name="VGA Cable")],
        added=[_item("SKU-076", name="Stream Deck Mini", qty=15)],
        quality_issues=[
            QualityIssue(sku="SKU-045", issue_type="duplicate_sku",
                         detail="row 54: duplicate", source="snapshot_2"),
        ],
    )


# ── write_json ─────────────────────────────────────────────────────────────

def test_write_json_creates_file(tmp_path):
    report = _sample_report()
    out = tmp_path / "report.json"
    write_json(report, out)
    assert out.exists()


def test_write_json_structure(tmp_path):
    report = _sample_report()
    out = tmp_path / "report.json"
    write_json(report, out)
    data = json.loads(out.read_text(encoding="utf-8"))

    assert "summary" in data
    assert "quantity_changed" in data
    assert "name_changed" in data
    assert "location_changed" in data
    assert "removed" in data
    assert "added" in data
    assert "quality_issues" in data


def test_write_json_summary_values(tmp_path):
    report = _sample_report()
    out = tmp_path / "report.json"
    write_json(report, out)
    summary = json.loads(out.read_text())["summary"]

    assert summary["unchanged_count"] == 1
    assert summary["quantity_changed_count"] == 1
    assert summary["removed_count"] == 1
    assert summary["added_count"] == 1
    assert summary["net_quantity_delta"] == -5


def test_write_json_quantity_change_fields(tmp_path):
    report = _sample_report()
    out = tmp_path / "report.json"
    write_json(report, out)
    qc = json.loads(out.read_text())["quantity_changed"][0]

    assert qc["sku"] == "SKU-001"
    assert qc["old_quantity"] == 150
    assert qc["new_quantity"] == 145
    assert qc["delta"] == -5


def test_write_json_name_change_fields(tmp_path):
    report = _sample_report()
    out = tmp_path / "report.json"
    write_json(report, out)
    nc = json.loads(out.read_text())["name_changed"][0]

    assert nc["sku"] == "SKU-045"
    assert nc["old_name"] == "Multimeter Pro"
    assert nc["new_name"] == "Multimeter Professional"


def test_write_json_creates_parent_dirs(tmp_path):
    out = tmp_path / "deep" / "nested" / "report.json"
    write_json(_sample_report(), out)
    assert out.exists()


# ── write_csv ──────────────────────────────────────────────────────────────

def test_write_csv_creates_file(tmp_path):
    out = tmp_path / "report.csv"
    write_csv(_sample_report(), out)
    assert out.exists()


def test_write_csv_has_correct_headers(tmp_path):
    out = tmp_path / "report.csv"
    write_csv(_sample_report(), out)
    with open(out, newline="", encoding="utf-8") as fh:
        headers = next(csv.reader(fh))
    assert headers == [
        "sku", "status", "name", "location",
        "old_quantity", "new_quantity", "delta", "pct_change",
    ]


def test_write_csv_quantity_changed_row(tmp_path):
    out = tmp_path / "report.csv"
    write_csv(_sample_report(), out)
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    changed = next(r for r in rows if r["status"] == "quantity_changed")
    assert changed["sku"] == "SKU-001"
    assert changed["delta"] == "-5"


def test_write_csv_removed_row(tmp_path):
    out = tmp_path / "report.csv"
    write_csv(_sample_report(), out)
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    removed = next(r for r in rows if r["status"] == "removed")
    assert removed["sku"] == "SKU-025"
    assert removed["old_quantity"] == "10"
    assert removed["new_quantity"] == "0"
    assert removed["pct_change"] == "-100.0"


def test_write_csv_added_row(tmp_path):
    out = tmp_path / "report.csv"
    write_csv(_sample_report(), out)
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    added = next(r for r in rows if r["status"] == "added")
    assert added["sku"] == "SKU-076"
    assert added["old_quantity"] == "0"
    assert added["new_quantity"] == "15"


def test_write_csv_rows_sorted_by_sku(tmp_path):
    out = tmp_path / "report.csv"
    write_csv(_sample_report(), out)
    with open(out, newline="", encoding="utf-8") as fh:
        skus = [r["sku"] for r in csv.DictReader(fh)]
    assert skus == sorted(skus)


def test_write_csv_empty_report_writes_only_header(tmp_path):
    out = tmp_path / "report.csv"
    write_csv(ReconciliationReport(), out)
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows == []


# ── write_quality_csv ──────────────────────────────────────────────────────

def test_write_quality_csv_creates_file(tmp_path):
    out = tmp_path / "quality.csv"
    write_quality_csv(_sample_report(), out)
    assert out.exists()


def test_write_quality_csv_has_correct_headers(tmp_path):
    out = tmp_path / "quality.csv"
    write_quality_csv(_sample_report(), out)
    with open(out, newline="", encoding="utf-8") as fh:
        headers = next(csv.reader(fh))
    assert headers == ["sku", "issue_type", "source", "detail"]


def test_write_quality_csv_row_content(tmp_path):
    out = tmp_path / "quality.csv"
    write_quality_csv(_sample_report(), out)
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["sku"] == "SKU-045"
    assert rows[0]["issue_type"] == "duplicate_sku"
    assert rows[0]["source"] == "snapshot_2"


def test_write_quality_csv_empty_issues(tmp_path):
    out = tmp_path / "quality.csv"
    write_quality_csv(ReconciliationReport(), out)
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows == []
