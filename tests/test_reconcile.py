"""Unit tests for the reconciliation engine."""
from src.models import InventoryItem
from src.reconcile import reconcile


def item(sku, name="Widget", qty=10, location="Warehouse A", date="2024-01-01"):
    return InventoryItem(
        sku=sku, name=name, quantity=qty,
        location=location, last_counted=date,
    )


# ── basic classification ───────────────────────────────────────────────────

def test_unchanged_when_identical():
    r = reconcile([item("SKU-001")], [item("SKU-001")])
    assert len(r.unchanged) == 1
    assert not r.quantity_changed
    assert not r.removed
    assert not r.added


def test_quantity_decreased():
    r = reconcile([item("SKU-001", qty=10)], [item("SKU-001", qty=8)])
    assert len(r.quantity_changed) == 1
    c = r.quantity_changed[0]
    assert c.delta == -2
    assert c.pct_change == -20.0


def test_quantity_increased():
    r = reconcile([item("SKU-001", qty=50)], [item("SKU-001", qty=75)])
    assert r.quantity_changed[0].delta == 25


def test_removed_item():
    r = reconcile([item("SKU-001")], [])
    assert len(r.removed) == 1
    assert r.removed[0].sku == "SKU-001"


def test_added_item():
    r = reconcile([], [item("SKU-002")])
    assert len(r.added) == 1
    assert r.added[0].sku == "SKU-002"


def test_removed_and_added_simultaneously():
    r = reconcile([item("SKU-001")], [item("SKU-002")])
    assert [i.sku for i in r.removed] == ["SKU-001"]
    assert [i.sku for i in r.added] == ["SKU-002"]


# ── name & location changes ────────────────────────────────────────────────

def test_name_change_tracked_and_flagged_as_quality_issue():
    r = reconcile(
        [item("SKU-045", name="Multimeter Pro")],
        [item("SKU-045", name="Multimeter Professional")],
    )
    assert len(r.name_changed) == 1
    nc = r.name_changed[0]
    assert nc.old_name == "Multimeter Pro"
    assert nc.new_name == "Multimeter Professional"
    assert any(q.issue_type == "name_changed_across_snapshots" for q in r.quality_issues)


def test_location_change_tracked():
    r = reconcile(
        [item("SKU-001", location="Warehouse A")],
        [item("SKU-001", location="Warehouse B")],
    )
    assert len(r.location_changed) == 1
    lc = r.location_changed[0]
    assert lc.old_location == "Warehouse A"
    assert lc.new_location == "Warehouse B"


def test_item_with_multiple_changes_appears_in_all_relevant_buckets():
    """An item can have both a quantity change and a name change simultaneously."""
    r = reconcile(
        [item("SKU-001", name="Old Name", qty=10)],
        [item("SKU-001", name="New Name", qty=5)],
    )
    assert len(r.quantity_changed) == 1
    assert len(r.name_changed) == 1
    assert not r.unchanged  # must NOT appear as unchanged


# ── edge cases ─────────────────────────────────────────────────────────────

def test_pct_change_is_none_when_old_quantity_is_zero():
    r = reconcile([item("SKU-001", qty=0)], [item("SKU-001", qty=5)])
    assert r.quantity_changed[0].pct_change is None


def test_empty_snapshots_produce_empty_report():
    r = reconcile([], [])
    s = r.summary()
    assert s["unchanged_count"] == 0
    assert s["added_count"] == 0
    assert s["removed_count"] == 0


def test_summary_counts_are_correct():
    r = reconcile(
        [item("SKU-001", qty=10), item("SKU-002")],
        [item("SKU-001", qty=8), item("SKU-003")],
    )
    s = r.summary()
    assert s["quantity_changed_count"] == 1
    assert s["removed_count"] == 1
    assert s["added_count"] == 1
    assert s["net_quantity_delta"] == -2


def test_net_quantity_delta_sums_all_changes():
    r = reconcile(
        [item("SKU-001", qty=100), item("SKU-002", qty=50)],
        [item("SKU-001", qty=80), item("SKU-002", qty=60)],
    )
    assert r.summary()["net_quantity_delta"] == -10


def test_reconciliation_is_deterministic():
    a = [item(f"SKU-{i:03d}", qty=i) for i in range(1, 20)]
    b = [item(f"SKU-{i:03d}", qty=i + 1) for i in range(1, 20)]
    assert reconcile(a, b).summary() == reconcile(a, b).summary()


def test_external_quality_issues_are_forwarded():
    from src.models import QualityIssue
    pre_issue = QualityIssue(sku="SKU-001", issue_type="malformed_sku",
                             detail="raw=SKU001", source="loader")
    r = reconcile([item("SKU-001")], [item("SKU-001")], issues=[pre_issue])
    assert pre_issue in r.quality_issues
