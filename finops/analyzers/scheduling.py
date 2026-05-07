from __future__ import annotations
from datetime import date
from finops.analyzers.base import Analyzer
from finops.models import AzureResource, ResourceCost, Finding, Severity

_NON_PROD_ENVS = {"dev", "development", "staging", "test", "qa"}
_SCHEDULABLE_TYPES = {
    "microsoft.compute/virtualmachines",
    "microsoft.web/sites",
    "microsoft.compute/virtualmachinescalesets",
}


def _all_days_covered(daily_costs: dict[str, float]) -> bool:
    if len(daily_costs) < 7:
        return False
    dates = sorted(date.fromisoformat(d) for d in daily_costs)
    delta = (dates[-1] - dates[0]).days + 1
    return len(dates) == delta


class SchedulingAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "scheduling"

    def analyze(
        self,
        subscription_id: str,
        resources: list[AzureResource],
        costs: list[ResourceCost],
    ) -> list[Finding]:
        cost_by_rid = {c.resource_id: c for c in costs}
        findings = []

        for resource in resources:
            if resource.type.lower() not in _SCHEDULABLE_TYPES:
                continue
            env = resource.tags.get("environment", "").lower()
            if not env:
                rg = resource.resource_group.lower()
                env = next((e for e in _NON_PROD_ENVS if e in rg), "")
            if env not in _NON_PROD_ENVS:
                continue

            cost = cost_by_rid.get(resource.id)
            if not cost or not _all_days_covered(cost.daily_costs):
                continue

            findings.append(Finding(
                subscription_id=subscription_id,
                resource_group=resource.resource_group,
                resource_id=resource.id,
                resource_type=resource.type,
                severity=Severity.MEDIUM,
                category="Scheduling",
                estimated_monthly_savings_usd=round(cost.avg_daily_cost * 16, 2),
                recommendation=(
                    f"Recurso en entorno '{env}' está activo los 7 días de la semana. "
                    "Configure un horario de apagado fuera de horas de trabajo para reducir costos."
                ),
                metadata={"environment": env, "days_active": len(cost.daily_costs)},
            ))
        return findings
