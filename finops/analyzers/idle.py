from __future__ import annotations
from finops.analyzers.base import Analyzer
from finops.models import AzureResource, ResourceCost, Finding, Severity


class IdleAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "idle"

    def analyze(
        self,
        subscription_id: str,
        resources: list[AzureResource],
        costs: list[ResourceCost],
    ) -> list[Finding]:
        threshold = self.config.cost_thresholds.idle_resource_daily_usd
        cost_by_rid = {c.resource_id: c for c in costs}
        findings = []

        for resource in resources:
            cost = cost_by_rid.get(resource.id)
            if not cost or not cost.daily_costs:
                continue
            if all(v <= threshold for v in cost.daily_costs.values()):
                findings.append(Finding(
                    subscription_id=subscription_id,
                    resource_group=resource.resource_group,
                    resource_id=resource.id,
                    resource_type=resource.type,
                    severity=Severity.MEDIUM,
                    category="Idle",
                    estimated_monthly_savings_usd=cost.total_cost,
                    recommendation=(
                        f"Recurso con costo muy bajo (${cost.avg_daily_cost:.4f}/día). "
                        "Considere eliminarlo si no está en uso activo."
                    ),
                    metadata={"avg_daily_cost_usd": cost.avg_daily_cost},
                ))
        return findings
