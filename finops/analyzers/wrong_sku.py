from __future__ import annotations
from finops.analyzers.base import Analyzer
from finops.models import AzureResource, ResourceCost, Finding, Severity


class WrongSkuAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "wrong_sku"

    def analyze(
        self,
        subscription_id: str,
        resources: list[AzureResource],
        costs: list[ResourceCost],
    ) -> list[Finding]:
        findings = []
        for resource in resources:
            finding = self._check(subscription_id, resource)
            if finding:
                findings.append(finding)
        return findings

    def _check(self, subscription_id: str, resource: AzureResource) -> Finding | None:
        rtype = resource.type.lower()
        tier = (resource.sku_tier or "").lower()

        if rtype == "microsoft.storage/storageaccounts" and tier == "premium":
            return Finding(
                subscription_id=subscription_id,
                resource_group=resource.resource_group,
                resource_id=resource.id,
                resource_type=resource.type,
                severity=Severity.MEDIUM,
                category="WrongSku",
                estimated_monthly_savings_usd=0.0,
                recommendation=(
                    "Cuenta de almacenamiento usa SKU Premium. "
                    "Evalúe migrar a Standard LRS para reducir costos si el rendimiento lo permite."
                ),
                metadata={"sku_name": resource.sku_name, "sku_tier": resource.sku_tier},
            )

        if rtype == "microsoft.dbforpostgresql/flexibleservers" and tier == "businesscritical":
            return Finding(
                subscription_id=subscription_id,
                resource_group=resource.resource_group,
                resource_id=resource.id,
                resource_type=resource.type,
                severity=Severity.HIGH,
                category="WrongSku",
                estimated_monthly_savings_usd=0.0,
                recommendation=(
                    "PostgreSQL Flexible Server usa tier BusinessCritical. "
                    "Si no requiere alta disponibilidad, considere migrar a GeneralPurpose."
                ),
                metadata={"sku_name": resource.sku_name, "sku_tier": resource.sku_tier},
            )

        return None
