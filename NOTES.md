# Reconciliation Notes

## Approach

Three small modules: `loader` (parse + normalize + flag quality issues),
`reconcile` (set-diff on normalized SKU), `reporters` (JSON + CSV output).
Stdlib only — no pandas/pydantic. The dataset is tiny and the logic is
clearer without a dataframe abstraction. `InventoryItem` is a frozen
dataclass so it's hashable and safe to use as a map value.

The CLI entry is `python reconcile.py`. Outputs land in `output/`:
- `reconciliation_report.json` — full structured report with summary
- `reconciliation_report.csv` — flat per-SKU change log (added/removed/changed)
- `data_quality_issues.csv` — every flagged anomaly with row-level provenance

## Key decisions

- **SKU is the join key, but only after normalization.** Snapshot 2 has
  `SKU005`, `sku-008`, `SKU018` — all variants of the canonical `SKU-NNN`
  form. Without normalization these would show as removed-from-1 + added-to-2,
  which would be wrong. The normalization is also recorded as a quality issue
  so the source-system bug stays visible.
- **Schema differs between files** (`name`/`product_name`, `quantity`/`qty`,
  `location`/`warehouse`, `last_counted`/`updated_at`). The loader maps
  aliases to a canonical schema rather than hard-coding either file's headers.
- **Float quantities** like `70.0`, `80.00` are accepted and coerced to int
  (with a `quantity_format` flag). A non-integer like `70.5` would also coerce
  but be flagged — I'd rather surface a warning than reject the row.
- **Name changes are flagged, not silently merged.** SKU-045 went from
  "Multimeter Pro" → "Multimeter Professional". I treat that as a quality
  issue worth a human review, not just a rename to apply.
- **Duplicate SKU within a single snapshot**: keep the first row, flag the
  rest. SKU-045 in snapshot 2 appears twice (once correctly, once with qty=-5).
  Keeping both would corrupt the diff.

## Quality issues found in the actual data

- 3 malformed SKUs in snapshot 2: `SKU005`, `sku-008`, `SKU018`
- 4 names with leading/trailing whitespace across both files
- 1 negative quantity: SKU-045 row with qty=-5
- 1 duplicate SKU in snapshot 2: SKU-045 appears twice with different names
- 1 non-ISO date: SKU-035 has `01/15/2024` instead of `2024-01-15`
- 1 cross-snapshot rename: SKU-045 "Multimeter Pro" → "Multimeter Professional"

The duplicate + negative + rename all converge on SKU-045 — likely a single
source-system event (a returned/damaged unit logged incorrectly).

## Assumptions

- SKU is the canonical identifier. Two rows with the same normalized SKU
  refer to the same item even if names disagree.
- Quantity is the metric we're reconciling (no price column in the data).
- Location changes are tracked but not treated as quality issues — items
  legitimately move between warehouses.
- Snapshots are point-in-time and complete; absence of a SKU in snapshot 2
  means the item was sold out / removed, not that the row was lost.

## What I'd add for production

- Configurable thresholds (e.g. flag quantity drops > 50% as suspicious).
- Persist reports to a database for week-over-week trend analysis.
- Slack/email alert on critical issues (negative qty, large unexpected drops).
