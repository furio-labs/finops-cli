from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from finops.models import SubscriptionData
from finops.reporters.models import Report

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _monthly_evolution(sub: SubscriptionData) -> dict:
    months = sorted({day[:7] for c in sub.costs for day in c.daily_costs})
    resources = []
    for c in sorted(sub.costs, key=lambda x: x.total_cost, reverse=True):
        monthly: dict[str, float] = {}
        for day, amt in c.daily_costs.items():
            m = day[:7]
            monthly[m] = monthly.get(m, 0.0) + amt
        resources.append({
            "resource_id": c.resource_id,
            "name": c.resource_id.split("/")[-1],
            "type_short": c.resource_type.split("/")[-1],
            "resource_group": c.resource_group,
            "monthly": monthly,
            "total": c.total_cost,
        })
    max_cost = max((r["total"] for r in resources), default=0.01)
    return {"months": months, "resources": resources, "max_cost": max_cost}


def _heat_class(value: float, max_cost: float) -> str:
    if value <= 0:
        return "cost-zero"
    ratio = value / max_cost
    if ratio > 0.8:
        return "heat-high"
    if ratio > 0.6:
        return "heat-6"
    if ratio > 0.45:
        return "heat-5"
    if ratio > 0.3:
        return "heat-4"
    if ratio > 0.2:
        return "heat-3"
    if ratio > 0.1:
        return "heat-2"
    return "heat-1"


def _leaks_by_category(sub: SubscriptionData) -> list[dict]:
    order = ["Idle", "WrongSku", "Scheduling", "DevInProd", "Untagged"]
    cats: dict[str, dict] = {}
    for f in sub.findings:
        if f.category not in cats:
            cats[f.category] = {"category": f.category, "findings": [], "total_savings": 0.0}
        cats[f.category]["findings"].append(f)
        cats[f.category]["total_savings"] += f.estimated_monthly_savings_usd
    return sorted(cats.values(), key=lambda c: order.index(c["category"]) if c["category"] in order else 99)


class HtmlReporter:
    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
        )
        self._env.globals["heat_class"] = _heat_class

    def render(self, report: Report) -> str:
        template = self._env.get_template("report.html.j2")
        evolution = {
            sub.subscription_id: _monthly_evolution(sub)
            for sub in report.subscriptions
            if not sub.skipped
        }
        leaks = {
            sub.subscription_id: _leaks_by_category(sub)
            for sub in report.subscriptions
            if not sub.skipped
        }
        return template.render(report=report, evolution=evolution, leaks=leaks)
