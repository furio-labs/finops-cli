from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Any
from finops.models import SubscriptionData, Finding, Severity, AzureResource, ResourceCost, Invoice, AiInsight


@dataclass
class Report:
    generated_at: str
    date_from: str
    date_to: str
    subscriptions: list[SubscriptionData]

    @property
    def total_cost(self) -> float:
        return sum(s.total_cost for s in self.subscriptions)

    @property
    def total_estimated_savings(self) -> float:
        return sum(f.estimated_monthly_savings_usd for f in self.all_findings)

    @property
    def all_findings(self) -> list[Finding]:
        return [f for s in self.subscriptions for f in s.findings]

    def findings_by_severity(self) -> dict[str, list[Finding]]:
        result: dict[str, list[Finding]] = {s.name: [] for s in Severity}
        for f in self.all_findings:
            result[f.severity.name].append(f)
        return result


def _to_serializable(obj: Any) -> Any:
    if isinstance(obj, Severity):
        return obj.name
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_serializable(i) for i in obj]
    return obj


def report_to_json(report: Report) -> str:
    raw = asdict(report)
    return json.dumps(_to_serializable(raw), indent=2, ensure_ascii=False)


def _from_dict(data: dict) -> Report:
    subs = []
    for s in data["subscriptions"]:
        resources = [AzureResource(**r) for r in s["resources"]]
        costs = [
            ResourceCost(
                resource_id=c["resource_id"],
                resource_group=c["resource_group"],
                subscription_id=c["subscription_id"],
                resource_type=c["resource_type"],
                daily_costs=c["daily_costs"],
                publisher_type=c.get("publisher_type", "Azure"),
                service_name=c.get("service_name", ""),
            )
            for c in s["costs"]
        ]
        invoices = [Invoice(**i) for i in s["invoices"]]
        findings = [
            Finding(
                **{**f, "severity": Severity[f["severity"]]}
            )
            for f in s["findings"]
        ]
        ai_insights = [AiInsight(**i) for i in s.get("ai_insights", [])]
        subs.append(SubscriptionData(
            subscription_id=s["subscription_id"],
            subscription_name=s["subscription_name"],
            resources=resources,
            costs=costs,
            invoices=invoices,
            findings=findings,
            ai_insights=ai_insights,
            skipped=s.get("skipped", False),
            skip_reason=s.get("skip_reason"),
        ))
    return Report(
        generated_at=data["generated_at"],
        date_from=data["date_from"],
        date_to=data["date_to"],
        subscriptions=subs,
    )


def report_from_json(json_str: str) -> Report:
    return _from_dict(json.loads(json_str))
