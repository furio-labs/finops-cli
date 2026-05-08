from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class Severity(IntEnum):
    INFO = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __str__(self) -> str:
        return self.name


@dataclass
class AzureResource:
    id: str
    name: str
    type: str
    resource_group: str
    subscription_id: str
    location: str
    tags: dict[str, str]
    sku_name: Optional[str] = None
    sku_tier: Optional[str] = None


@dataclass
class ResourceCost:
    resource_id: str
    resource_group: str
    subscription_id: str
    resource_type: str
    daily_costs: dict[str, float]  # "YYYY-MM-DD" -> USD
    publisher_type: str = "Azure"  # "Azure" | "Marketplace"
    service_name: str = ""

    @property
    def total_cost(self) -> float:
        return sum(self.daily_costs.values())

    @property
    def avg_daily_cost(self) -> float:
        if not self.daily_costs:
            return 0.0
        return self.total_cost / len(self.daily_costs)


@dataclass
class Invoice:
    id: str
    name: str
    subscription_id: str
    billing_period: str
    amount_due: float
    currency: str
    status: str
    due_date: Optional[str] = None
    pdf_url: Optional[str] = None


@dataclass
class Finding:
    subscription_id: str
    resource_group: str
    resource_id: str
    resource_type: str
    severity: Severity
    category: str
    estimated_monthly_savings_usd: float
    recommendation: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SubscriptionData:
    subscription_id: str
    subscription_name: str
    resources: list[AzureResource]
    costs: list[ResourceCost]
    invoices: list[Invoice]
    findings: list[Finding] = field(default_factory=list)
    skipped: bool = False
    skip_reason: Optional[str] = None

    @property
    def total_cost(self) -> float:
        return sum(c.total_cost for c in self.costs)
