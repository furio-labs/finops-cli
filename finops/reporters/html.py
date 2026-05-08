from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from finops.models import SubscriptionData, ResourceCost
from finops.reporters.models import Report

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _parse_service_name(cost: ResourceCost) -> str:
    """Extract human-readable name from a marketplace resource ID.

    ARM marketplace SaaS IDs: .../providers/microsoft.saas/resources/{name}-{uuid}-{uuid}
    Stop at the first all-hex segment (>= 8 chars) to get {name}.
    """
    basename = cost.resource_id.split("/")[-1]
    parts = basename.split("-")
    name_parts = []
    for p in parts:
        if len(p) >= 8 and all(c in "0123456789abcdef" for c in p.lower()):
            break
        name_parts.append(p)
    name = "-".join(name_parts).strip("-") if name_parts else ""
    return name or cost.service_name or cost.resource_type.split("/")[-1]


def _build_monthly(costs: list[ResourceCost]) -> tuple[list[str], dict[str, float]]:
    """Return (sorted_months, {month -> total_cost}) for a list of ResourceCost objects."""
    monthly: dict[str, float] = {}
    for c in costs:
        for day, amt in c.daily_costs.items():
            m = day[:7]
            monthly[m] = monthly.get(m, 0.0) + amt
    return sorted(monthly), monthly


def _rg_monthly(sub: SubscriptionData) -> dict:
    """Pre-compute per-resource-group monthly costs (Azure-only, excludes marketplace)."""
    azure_costs = [c for c in sub.costs if c.publisher_type.lower() != "marketplace"]
    months, _ = _build_monthly(azure_costs)

    rg_map: dict[str, dict] = {}
    for c in azure_costs:
        rg = c.resource_group or "(sin grupo)"
        if rg not in rg_map:
            rg_map[rg] = {"monthly": {}, "total": 0.0, "count": 0}
        rg_map[rg]["count"] += 1
        for day, amt in c.daily_costs.items():
            m = day[:7]
            rg_map[rg]["monthly"][m] = rg_map[rg]["monthly"].get(m, 0.0) + amt
            rg_map[rg]["total"] += amt

    rgs = sorted(
        [{"name": k, **v} for k, v in rg_map.items()],
        key=lambda x: x["total"],
        reverse=True,
    )

    monthly_totals: dict[str, float] = {}
    for rg in rgs:
        for m, v in rg["monthly"].items():
            monthly_totals[m] = monthly_totals.get(m, 0.0) + v

    max_monthly = max(monthly_totals.values(), default=0.01)

    return {
        "months": months,
        "rgs": rgs,
        "monthly_totals": monthly_totals,
        "max_monthly": max_monthly,
    }


def _marketplace_section(sub: SubscriptionData) -> dict | None:
    mp_costs = [c for c in sub.costs if c.publisher_type.lower() == "marketplace"]
    if not mp_costs:
        return None

    months, _ = _build_monthly(mp_costs)
    total_all = sum(c.total_cost for c in sub.costs) or 1.0

    entries = []
    for c in sorted(mp_costs, key=lambda x: x.total_cost, reverse=True):
        monthly: dict[str, float] = {}
        for day, amt in c.daily_costs.items():
            m = day[:7]
            monthly[m] = monthly.get(m, 0.0) + amt
        entries.append({
            "name": _parse_service_name(c),
            "resource_id": c.resource_id,
            "resource_type": c.resource_type,
            "resource_group": c.resource_group,
            "service_name": c.service_name,
            "monthly": monthly,
            "total": c.total_cost,
            "pct_of_sub": c.total_cost / total_all * 100,
        })

    mp_total = sum(e["total"] for e in entries)
    monthly_totals: dict[str, float] = {}
    for e in entries:
        for m, v in e["monthly"].items():
            monthly_totals[m] = monthly_totals.get(m, 0.0) + v

    return {
        "entries": entries,
        "months": months,
        "monthly_totals": monthly_totals,
        "total": mp_total,
        "pct_of_sub": mp_total / total_all * 100,
    }


def _monthly_evolution(sub: SubscriptionData) -> dict:
    """Azure-only monthly evolution — marketplace resources excluded (they have their own section)."""
    azure_costs = [c for c in sub.costs if c.publisher_type.lower() != "marketplace"]
    months, _ = _build_monthly(azure_costs)

    resources = []
    for c in sorted(azure_costs, key=lambda x: x.total_cost, reverse=True):
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
    marketplace_total = sum(c.total_cost for c in sub.costs if c.publisher_type.lower() == "marketplace")
    return {
        "months": months,
        "resources": resources,
        "max_cost": max_cost,
        "marketplace_total": marketplace_total,
        "azure_total": sub.total_cost - marketplace_total,
    }


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
        marketplace = {
            sub.subscription_id: _marketplace_section(sub)
            for sub in report.subscriptions
            if not sub.skipped
        }
        rg_data = {
            sub.subscription_id: _rg_monthly(sub)
            for sub in report.subscriptions
            if not sub.skipped
        }
        return template.render(
            report=report,
            evolution=evolution,
            leaks=leaks,
            marketplace=marketplace,
            rg_data=rg_data,
        )
