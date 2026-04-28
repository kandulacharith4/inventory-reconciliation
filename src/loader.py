"""CSV loading with schema normalisation and quality-issue detection."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .models import InventoryItem, QualityIssue


# Maps every column name we've seen in the wild to a canonical field name.
SCHEMA_ALIASES: dict[str, str] = {
    "sku": "sku",
    "name": "name",
    "product_name": "name",
    "quantity": "quantity",
    "qty": "quantity",
    "location": "location",
    "warehouse": "location",
    "last_counted": "last_counted",
    "updated_at": "last_counted",
}

_SKU_CANONICAL = re.compile(r"^SKU-\d{3,}$")
_DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_sku(raw: str) -> str:
    """Collapse SKU-001 / sku-001 / SKU001 to the canonical SKU-NNN form."""
    s = raw.strip().upper()
    m = re.match(r"^SKU-?(\d+)$", s)
    if m:
        return f"SKU-{m.group(1).zfill(3)}"
    return s


def normalize_quantity(raw: str) -> tuple[int, str | None]:
    """Return ``(quantity, error_message_or_None)``.

    Accepts integer strings, floats with zero fractional part (``70.0``),
    and coerces non-integer floats (``70.5``) with a warning rather than
    rejecting the row outright.
    """
    s = raw.strip()
    if not s:
        return 0, "empty quantity"
    try:
        f = float(s)
    except ValueError:
        return 0, f"unparseable quantity: {raw!r}"
    if f != int(f):
        return int(f), f"non-integer quantity coerced: {raw!r}"
    return int(f), None


def load_snapshot(
    path: Path, source_label: str
) -> tuple[list[InventoryItem], list[QualityIssue]]:
    """Parse *path* into a deduplicated list of :class:`InventoryItem` objects.

    Any data-quality anomaly is appended to the returned issues list rather
    than raising an exception, so the caller gets as much data as possible.
    Duplicate SKUs keep the *first* occurrence; subsequent rows are flagged.
    """
    items: list[InventoryItem] = []
    issues: list[QualityIssue] = []
    seen_skus: dict[str, InventoryItem] = {}

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header row")

        field_map = {
            col: SCHEMA_ALIASES.get(col.strip().lower())
            for col in reader.fieldnames
        }
        required = {"sku", "name", "quantity", "location", "last_counted"}
        mapped = {v for v in field_map.values() if v}
        missing = required - mapped
        if missing:
            raise ValueError(f"{path} is missing required columns: {missing}")

        for row_num, row in enumerate(reader, start=2):
            norm = {
                field_map[k]: (v or "")
                for k, v in row.items()
                if field_map.get(k)
            }

            raw_sku: str = norm["sku"]
            raw_name: str = norm["name"]
            sku = normalize_sku(raw_sku)
            name = raw_name.strip()
            location = norm["location"].strip()
            last_counted = norm["last_counted"].strip()

            # --- quality checks -------------------------------------------
            if not _SKU_CANONICAL.match(raw_sku.strip()):
                issues.append(QualityIssue(
                    sku=sku, issue_type="malformed_sku",
                    detail=f"row {row_num}: raw={raw_sku!r} normalised to {sku!r}",
                    source=source_label,
                ))

            if raw_name != name:
                issues.append(QualityIssue(
                    sku=sku, issue_type="whitespace_in_name",
                    detail=f"row {row_num}: name={raw_name!r}",
                    source=source_label,
                ))

            qty, qty_err = normalize_quantity(norm["quantity"])
            if qty_err:
                issues.append(QualityIssue(
                    sku=sku, issue_type="quantity_format",
                    detail=f"row {row_num}: {qty_err}",
                    source=source_label,
                ))
            if qty < 0:
                issues.append(QualityIssue(
                    sku=sku, issue_type="negative_quantity",
                    detail=f"row {row_num}: qty={qty}",
                    source=source_label,
                ))

            if not _DATE_ISO.match(last_counted):
                issues.append(QualityIssue(
                    sku=sku, issue_type="date_format",
                    detail=f"row {row_num}: last_counted={last_counted!r}",
                    source=source_label,
                ))

            if not name:
                issues.append(QualityIssue(
                    sku=sku, issue_type="missing_name",
                    detail=f"row {row_num}",
                    source=source_label,
                ))

            item = InventoryItem(
                sku=sku, name=name, quantity=qty,
                location=location, last_counted=last_counted,
            )

            if sku in seen_skus:
                prev = seen_skus[sku]
                issues.append(QualityIssue(
                    sku=sku, issue_type="duplicate_sku",
                    detail=(
                        f"row {row_num}: duplicate of earlier row "
                        f"(prev: name={prev.name!r} qty={prev.quantity}; "
                        f"this: name={name!r} qty={qty})"
                    ),
                    source=source_label,
                ))
                continue  # keep first occurrence

            seen_skus[sku] = item
            items.append(item)

    return items, issues
