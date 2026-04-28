"""Output formatters — write reconciliation results to JSON and CSV."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import ReconciliationReport


def write_json(report: ReconciliationReport, path: Path) -> None:
    """Write the full report as a structured JSON file."""
    payload = {
        "summary": report.summary(),
        "unchanged": [i.to_dict() for i in report.unchanged],
        "quantity_changed": [c.to_dict() for c in report.quantity_changed],
        "name_changed": [n.to_dict() for n in report.name_changed],
        "location_changed": [lc.to_dict() for lc in report.location_changed],
        "removed": [i.to_dict() for i in report.removed],
        "added": [i.to_dict() for i in report.added],
        "quality_issues": [q.to_dict() for q in report.quality_issues],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(report: ReconciliationReport, path: Path) -> None:
    """Write a flat per-SKU change log (added / removed / quantity_changed).

    Unchanged items are intentionally excluded — this file is a *delta* report
    intended for operational review.  The full dataset lives in the JSON output.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []

    for c in report.quantity_changed:
        rows.append({
            "sku": c.sku,
            "status": "quantity_changed",
            "name": c.name,
            "location": c.location,
            "old_quantity": c.old_quantity,
            "new_quantity": c.new_quantity,
            "delta": c.delta,
            "pct_change": c.pct_change,
        })

    for i in report.removed:
        rows.append({
            "sku": i.sku,
            "status": "removed",
            "name": i.name,
            "location": i.location,
            "old_quantity": i.quantity,
            "new_quantity": 0,
            "delta": -i.quantity,
            "pct_change": -100.0,
        })

    for i in report.added:
        rows.append({
            "sku": i.sku,
            "status": "added",
            "name": i.name,
            "location": i.location,
            "old_quantity": 0,
            "new_quantity": i.quantity,
            "delta": i.quantity,
            "pct_change": None,
        })

    fieldnames = [
        "sku", "status", "name", "location",
        "old_quantity", "new_quantity", "delta", "pct_change",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["sku"]))


def write_quality_csv(report: ReconciliationReport, path: Path) -> None:
    """Write every flagged data-quality anomaly with full row-level provenance."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["sku", "issue_type", "source", "detail"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for q in report.quality_issues:
            writer.writerow(q.to_dict())
