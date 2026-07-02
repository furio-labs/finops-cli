from __future__ import annotations
from finops.analyzers.base import Analyzer
from finops.models import CloudResource, ResourceCost, Finding, Severity


class UntaggedAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "untagged"

    def analyze(
        self,
        subscription_id: str,
        resources: list[CloudResource],
        costs: list[ResourceCost],
    ) -> list[Finding]:
        findings = []
        for resource in resources:
            missing = [t for t in self.config.required_tags if t not in resource.tags]
            if not missing:
                continue
            findings.append(Finding(
                subscription_id=subscription_id,
                resource_group=resource.resource_group,
                resource_id=resource.id,
                resource_type=resource.type,
                severity=Severity.HIGH,
                category="Untagged",
                estimated_monthly_savings_usd=0.0,
                recommendation=(
                    f"Recurso sin etiquetas requeridas: {', '.join(missing)}. "
                    "Agregue las etiquetas para una correcta asignación de costos."
                ),
                metadata={"missing_tags": missing},
                provider=resource.provider,
            ))
        return findings
