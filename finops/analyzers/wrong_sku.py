from __future__ import annotations
from finops.analyzers.base import Analyzer
from finops.models import CloudResource, ResourceCost, Finding, Severity


class WrongSkuAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "wrong_sku"

    def analyze(
        self,
        subscription_id: str,
        resources: list[CloudResource],
        costs: list[ResourceCost],
    ) -> list[Finding]:
        findings = []
        for resource in resources:
            finding = self._check(subscription_id, resource)
            if finding:
                findings.append(finding)
        return findings

    def _check(self, subscription_id: str, resource: CloudResource) -> Finding | None:
        if resource.provider == "gcp":
            return self._check_gcp(subscription_id, resource)
        if resource.provider == "aws":
            # No SKU checks for AWS yet: the Resource Groups Tagging API
            # (finops/collectors/aws/resources.py) doesn't return instance
            # type/storage class, so there's nothing to key a SKU check on.
            return None
        return self._check_azure(subscription_id, resource)

    def _finding(self, subscription_id, resource, severity, recommendation) -> Finding:
        return Finding(
            subscription_id=subscription_id,
            resource_group=resource.resource_group,
            resource_id=resource.id,
            resource_type=resource.type,
            severity=severity,
            category="WrongSku",
            estimated_monthly_savings_usd=0.0,
            recommendation=recommendation,
            metadata={"sku_name": resource.sku_name, "sku_tier": resource.sku_tier},
            provider=resource.provider,
        )

    def _check_azure(self, subscription_id: str, resource: CloudResource) -> Finding | None:
        rtype = resource.type.lower()
        tier = (resource.sku_tier or "").lower()

        if rtype == "microsoft.storage/storageaccounts" and tier == "premium":
            return self._finding(
                subscription_id, resource, Severity.MEDIUM,
                "Cuenta de almacenamiento usa SKU Premium. "
                "Evalúe migrar a Standard LRS para reducir costos si el rendimiento lo permite.",
            )

        if rtype == "microsoft.dbforpostgresql/flexibleservers" and tier == "businesscritical":
            return self._finding(
                subscription_id, resource, Severity.HIGH,
                "PostgreSQL Flexible Server usa tier BusinessCritical. "
                "Si no requiere alta disponibilidad, considere migrar a GeneralPurpose.",
            )

        return None

    def _check_gcp(self, subscription_id: str, resource: CloudResource) -> Finding | None:
        rtype = resource.type.lower()
        name = (resource.sku_name or "").lower()

        if rtype == "sqladmin.googleapis.com/instance" and "highmem" in name:
            return self._finding(
                subscription_id, resource, Severity.HIGH,
                "Cloud SQL usa un tier high-memory. "
                "Evalúe un tier estándar o menor si la carga de trabajo lo permite.",
            )

        if rtype == "compute.googleapis.com/disk" and name in {"pd-ssd", "pd-extreme", "hyperdisk-extreme"}:
            return self._finding(
                subscription_id, resource, Severity.MEDIUM,
                "Disco persistente SSD/Extreme. "
                "Evalúe pd-balanced o pd-standard para reducir costos si el rendimiento lo permite.",
            )

        return None
