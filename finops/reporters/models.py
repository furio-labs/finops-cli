from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Any
from finops.models import (
    Severity, AzureResource, ResourceCost, Invoice, Finding, SubscriptionData
)


@dataclass
class Report:
    generated_at: str
    date_from: str
    date_to: str
    subscriptions: list[SubscriptionData] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(s.total_cost for s in self.subscriptions if not s.skipped)

    @property
    def total_estimated_savings(self) -> float:
        return sum(
            f.estimated_monthly_savings_usd
            for s in self.subscriptions
            for f in s.findings
        )

    @property
    def all_findings(self) -> list[Finding]:
        return [f for s in self.subscriptions for f in s.findings]

    def findings_by_severity(self) -> dict[str, list[Finding]]:
        result: dict[str, list[Finding]] = {}
        for f in self.all_findings:
            key = str(f.severity)
            result.setdefault(key, []).append(f)
        return result


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    return {
        "subscription_id": f.subscription_id,
        "resource_group": f.resource_group,
        "resource_id": f.resource_id,
        "resource_type": f.resource_type,
        "severity": f.severity.value,
        "category": f.category,
        "estimated_monthly_savings_usd": f.estimated_monthly_savings_usd,
        "recommendation": f.recommendation,
        "metadata": f.metadata,
    }


def _invoice_to_dict(inv: Invoice) -> dict[str, Any]:
    return {
        "id": inv.id,
        "name": inv.name,
        "subscription_id": inv.subscription_id,
        "billing_period": inv.billing_period,
        "amount_due": inv.amount_due,
        "currency": inv.currency,
        "status": inv.status,
        "due_date": inv.due_date,
        "pdf_url": inv.pdf_url,
    }


def _resource_to_dict(r: AzureResource) -> dict[str, Any]:
    return {
        "id": r.id,
        "name": r.name,
        "type": r.type,
        "resource_group": r.resource_group,
        "subscription_id": r.subscription_id,
        "location": r.location,
        "tags": r.tags,
        "sku_name": r.sku_name,
        "sku_tier": r.sku_tier,
    }


def _cost_to_dict(c: ResourceCost) -> dict[str, Any]:
    return {
        "resource_id": c.resource_id,
        "resource_group": c.resource_group,
        "subscription_id": c.subscription_id,
        "resource_type": c.resource_type,
        "daily_costs": c.daily_costs,
    }


def _sub_to_dict(s: SubscriptionData) -> dict[str, Any]:
    return {
        "subscription_id": s.subscription_id,
        "subscription_name": s.subscription_name,
        "skipped": s.skipped,
        "skip_reason": s.skip_reason,
        "resources": [_resource_to_dict(r) for r in s.resources],
        "costs": [_cost_to_dict(c) for c in s.costs],
        "invoices": [_invoice_to_dict(inv) for inv in s.invoices],
        "findings": [_finding_to_dict(f) for f in s.findings],
    }


def report_to_json(report: Report) -> str:
    data = {
        "generated_at": report.generated_at,
        "date_from": report.date_from,
        "date_to": report.date_to,
        "subscriptions": [_sub_to_dict(s) for s in report.subscriptions],
    }
    return json.dumps(data, indent=2)


def _sub_from_dict(d: dict[str, Any]) -> SubscriptionData:
    resources = [
        AzureResource(
            id=r["id"], name=r["name"], type=r["type"],
            resource_group=r["resource_group"], subscription_id=r["subscription_id"],
            location=r["location"], tags=r.get("tags", {}),
            sku_name=r.get("sku_name"), sku_tier=r.get("sku_tier"),
        )
        for r in d.get("resources", [])
    ]
    costs = [
        ResourceCost(
            resource_id=c["resource_id"], resource_group=c["resource_group"],
            subscription_id=c["subscription_id"], resource_type=c["resource_type"],
            daily_costs=c["daily_costs"],
        )
        for c in d.get("costs", [])
    ]
    invoices = [
        Invoice(
            id=inv["id"], name=inv["name"], subscription_id=inv["subscription_id"],
            billing_period=inv["billing_period"], amount_due=inv["amount_due"],
            currency=inv["currency"], status=inv["status"],
            due_date=inv.get("due_date"), pdf_url=inv.get("pdf_url"),
        )
        for inv in d.get("invoices", [])
    ]
    findings = [
        Finding(
            subscription_id=f["subscription_id"], resource_group=f["resource_group"],
            resource_id=f["resource_id"], resource_type=f["resource_type"],
            severity=Severity(f["severity"]), category=f["category"],
            estimated_monthly_savings_usd=f["estimated_monthly_savings_usd"],
            recommendation=f["recommendation"],
            metadata=f.get("metadata", {}),
        )
        for f in d.get("findings", [])
    ]
    return SubscriptionData(
        subscription_id=d["subscription_id"],
        subscription_name=d["subscription_name"],
        resources=resources,
        costs=costs,
        invoices=invoices,
        findings=findings,
        skipped=d.get("skipped", False),
        skip_reason=d.get("skip_reason"),
    )


def report_from_json(json_str: str) -> Report:
    data = json.loads(json_str)
    return Report(
        generated_at=data["generated_at"],
        date_from=data["date_from"],
        date_to=data["date_to"],
        subscriptions=[_sub_from_dict(s) for s in data.get("subscriptions", [])],
    )
