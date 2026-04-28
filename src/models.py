from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass(frozen=True)
class InventoryItem:
    sku: str
    name: str
    quantity: int
    location: str
    last_counted: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QualityIssue:
    sku: str
    issue_type: str
    detail: str
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QuantityChange:
    sku: str
    name: str
    location: str
    old_quantity: int
    new_quantity: int

    @property
    def delta(self) -> int:
        return self.new_quantity - self.old_quantity

    @property
    def pct_change(self) -> Optional[float]:
        if self.old_quantity == 0:
            return None
        return round((self.delta / self.old_quantity) * 100, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["delta"] = self.delta
        d["pct_change"] = self.pct_change
        return d


@dataclass
class NameChange:
    sku: str
    old_name: str
    new_name: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LocationChange:
    sku: str
    old_location: str
    new_location: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReconciliationReport:
    unchanged: list[InventoryItem] = field(default_factory=list)
    quantity_changed: list[QuantityChange] = field(default_factory=list)
    name_changed: list[NameChange] = field(default_factory=list)
    location_changed: list[LocationChange] = field(default_factory=list)
    removed: list[InventoryItem] = field(default_factory=list)
    added: list[InventoryItem] = field(default_factory=list)
    quality_issues: list[QualityIssue] = field(default_factory=list)

    def summary(self) -> dict:
        net_delta = sum(c.delta for c in self.quantity_changed)
        return {
            "unchanged_count": len(self.unchanged),
            "quantity_changed_count": len(self.quantity_changed),
            "name_changed_count": len(self.name_changed),
            "location_changed_count": len(self.location_changed),
            "removed_count": len(self.removed),
            "added_count": len(self.added),
            "quality_issues_count": len(self.quality_issues),
            "net_quantity_delta": net_delta,
        }
