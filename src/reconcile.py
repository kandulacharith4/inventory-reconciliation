"""Core reconciliation logic — pure functions, no I/O."""
from __future__ import annotations

from .models import (
    InventoryItem,
    LocationChange,
    NameChange,
    QuantityChange,
    QualityIssue,
    ReconciliationReport,
)


def reconcile(
    snapshot1: list[InventoryItem],
    snapshot2: list[InventoryItem],
    issues: list[QualityIssue] | None = None,
) -> ReconciliationReport:
    """Compare two snapshots and return a fully-populated :class:`ReconciliationReport`.

    Items are matched on normalised SKU.  An item can appear in more than one
    change bucket (e.g. both ``quantity_changed`` and ``name_changed``) if
    multiple fields differ — see NOTES.md for the rationale.
    """
    by_sku_1: dict[str, InventoryItem] = {i.sku: i for i in snapshot1}
    by_sku_2: dict[str, InventoryItem] = {i.sku: i for i in snapshot2}

    report = ReconciliationReport(quality_issues=list(issues or []))

    for sku, a in by_sku_1.items():
        b = by_sku_2.get(sku)
        if b is None:
            report.removed.append(a)
            continue

        changed = False

        if a.quantity != b.quantity:
            changed = True
            report.quantity_changed.append(QuantityChange(
                sku=sku,
                name=b.name,
                location=b.location,
                old_quantity=a.quantity,
                new_quantity=b.quantity,
            ))

        if a.name != b.name:
            changed = True
            report.name_changed.append(NameChange(
                sku=sku,
                old_name=a.name,
                new_name=b.name,
            ))
            # Name drift between snapshots is a data-quality signal, not just a
            # rename — flag it so a human can decide whether to update the master.
            report.quality_issues.append(QualityIssue(
                sku=sku,
                issue_type="name_changed_across_snapshots",
                detail=f"{a.name!r} -> {b.name!r}",
                source="reconcile",
            ))

        if a.location != b.location:
            changed = True
            report.location_changed.append(LocationChange(
                sku=sku,
                old_location=a.location,
                new_location=b.location,
            ))

        if not changed:
            report.unchanged.append(b)

    for sku, b in by_sku_2.items():
        if sku not in by_sku_1:
            report.added.append(b)

    return report
