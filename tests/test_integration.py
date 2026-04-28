"""End-to-end integration tests using the actual snapshot files.

These tests assert facts we know to be true from manual inspection of the
data (documented in NOTES.md).  They act as a regression guard: if the
loader, reconciler, or reporters break on real-world input, these fail.
"""
import json
from pathlib import Path

import pytest

from src.loader import load_snapshot
from src.reconcile import reconcile
from src.reporters import write_json, write_csv, write_quality_csv

SNAPSHOT_1 = Path("data/snapshot_1.csv")
SNAPSHOT_2 = Path("data/snapshot_2.csv")


@pytest.fixture(scope="module")
def report():
    s1, issues1 = load_snapshot(SNAPSHOT_1, "snapshot_1")
    s2, issues2 = load_snapshot(SNAPSHOT_2, "snapshot_2")
    return reconcile(s1, s2, issues=issues1 + issues2)


# ── known data-quality facts ───────────────────────────────────────────────

def test_detects_negative_quantity(report):
    """SKU-045 row in snapshot 2 has qty=-5."""
    issue_types = [q.issue_type for q in report.quality_issues]
    assert "negative_quantity" in issue_types


def test_detects_duplicate_sku(report):
    """SKU-045 appears twice in snapshot 2."""
    issue_types = [q.issue_type for q in report.quality_issues]
    assert "duplicate_sku" in issue_types


def test_detects_malformed_skus(report):
    """snapshot 2 contains SKU005, sku-008, SKU018."""
    malformed = [q for q in report.quality_issues if q.issue_type == "malformed_sku"]
    assert len(malformed) >= 3


def test_detects_non_iso_date(report):
    """SKU-035 in snapshot 2 has date '01/15/2024'."""
    date_issues = [q for q in report.quality_issues if q.issue_type == "date_format"]
    assert len(date_issues) >= 1


def test_detects_name_change_for_sku_045(report):
    """SKU-045: 'Multimeter Pro' -> 'Multimeter Professional'."""
    name_issues = [
        q for q in report.quality_issues
        if q.issue_type == "name_changed_across_snapshots" and q.sku == "SKU-045"
    ]
    assert len(name_issues) == 1


# ── known reconciliation facts ─────────────────────────────────────────────

def test_vga_cable_removed(report):
    """SKU-025 (VGA Cable) is in snapshot 1 but not snapshot 2."""
    removed_skus = {i.sku for i in report.removed}
    assert "SKU-025" in removed_skus


def test_dvi_cable_removed(report):
    """SKU-026 (DVI Cable) is in snapshot 1 but not snapshot 2."""
    removed_skus = {i.sku for i in report.removed}
    assert "SKU-026" in removed_skus


def test_stream_deck_mini_added(report):
    """SKU-076 (Stream Deck Mini) is new in snapshot 2."""
    added_skus = {i.sku for i in report.added}
    assert "SKU-076" in added_skus


def test_new_items_count(report):
    """Snapshot 2 has 5 new SKUs: 076–080."""
    assert len(report.added) == 5


def test_sku_006_is_unchanged(report):
    """SKU-006 (Connector Cable 10ft) has qty=350 in both snapshots."""
    unchanged_skus = {i.sku for i in report.unchanged}
    assert "SKU-006" in unchanged_skus


def test_widget_a_quantity_decreased(report):
    """SKU-001 went from 150 to 145."""
    change = next(c for c in report.quantity_changed if c.sku == "SKU-001")
    assert change.old_quantity == 150
    assert change.new_quantity == 145
    assert change.delta == -5


# ── output files round-trip ────────────────────────────────────────────────

def test_json_output_round_trips(report, tmp_path):
    out = tmp_path / "report.json"
    write_json(report, out)
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["summary"]["added_count"] == len(report.added)
    assert data["summary"]["removed_count"] == len(report.removed)
    assert data["summary"]["quality_issues_count"] == len(report.quality_issues)


def test_csv_output_contains_all_changes(report, tmp_path):
    import csv as _csv
    out = tmp_path / "report.csv"
    write_csv(report, out)
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(_csv.DictReader(fh))

    statuses = {r["status"] for r in rows}
    assert "added" in statuses
    assert "removed" in statuses
    assert "quantity_changed" in statuses


def test_quality_csv_has_all_issues(report, tmp_path):
    import csv as _csv
    out = tmp_path / "quality.csv"
    write_quality_csv(report, out)
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(_csv.DictReader(fh))
    assert len(rows) == len(report.quality_issues)
