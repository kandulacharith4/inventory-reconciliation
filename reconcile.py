"""CLI entry point for inventory reconciliation."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.loader import load_snapshot
from src.reconcile import reconcile
from src.reporters import write_csv, write_json, write_quality_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile two inventory snapshots.")
    parser.add_argument("--snapshot1", default="data/snapshot_1.csv", type=Path)
    parser.add_argument("--snapshot2", default="data/snapshot_2.csv", type=Path)
    parser.add_argument("--output-dir", default="output", type=Path)
    args = parser.parse_args(argv)

    s1, issues1 = load_snapshot(args.snapshot1, "snapshot_1")
    s2, issues2 = load_snapshot(args.snapshot2, "snapshot_2")
    report = reconcile(s1, s2, issues=issues1 + issues2)

    out = args.output_dir
    write_json(report, out / "reconciliation_report.json")
    write_csv(report, out / "reconciliation_report.csv")
    write_quality_csv(report, out / "data_quality_issues.csv")

    s = report.summary()
    print("Inventory Reconciliation Summary")
    print("-" * 40)
    print(f"  Snapshot 1: {len(s1)} items")
    print(f"  Snapshot 2: {len(s2)} items")
    for k, v in s.items():
        print(f"  {k}: {v}")
    print(f"\nReports written to: {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
