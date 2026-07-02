from __future__ import annotations
from finops.analyzers.base import Analyzer
from finops.models import CloudResource, ResourceCost, Finding, Severity

_DEV_ENV_VALUES = {"dev", "development", "staging", "test", "qa"}
_PROD_ENV_VALUES = {"production", "prod"}

# Azure SKU heuristics
_DEV_SKU_TIERS = {"burstable", "basic", "free", "shared"}
_DEV_SKU_PREFIXES = ("standard_b",)
_EXPENSIVE_VM_PREFIXES = ("standard_d", "standard_e", "standard_f", "standard_m", "standard_n")

# GCP machine-type heuristics (sku_name is the machine type, e.g. "e2-standard-4")
_GCP_DEV_MACHINE_TYPES = {"f1-micro", "g1-small", "e2-micro", "e2-small", "e2-medium"}
_GCP_EXPENSIVE_FAMILIES = ("n2", "n2d", "c2", "c2d", "c3", "m1", "m2", "m3", "a2")

_CHECK_TYPES = {
    "azure": {
        "microsoft.compute/virtualmachines",
        "microsoft.dbforpostgresql/flexibleservers",
        "microsoft.web/sites",
    },
    "gcp": {
        "compute.googleapis.com/instance",
    },
    # AWS intentionally has no entry here: the Resource Groups Tagging API
    # (finops/collectors/aws/resources.py) doesn't return instance type, so
    # there's no sku_name/sku_tier to check env-vs-SKU mismatches against.
}


def _env_from_resource(resource: CloudResource) -> str:
    env = resource.tags.get("environment", "").lower()
    if not env:
        rg = (resource.resource_group or "").lower()
        for val in _DEV_ENV_VALUES:
            if val in rg:
                return val
        for val in _PROD_ENV_VALUES:
            if val in rg:
                return "production"
    return env


def _is_dev_sku(resource: CloudResource) -> bool:
    name = (resource.sku_name or "").lower()
    if resource.provider == "gcp":
        return name in _GCP_DEV_MACHINE_TYPES
    tier = (resource.sku_tier or "").lower()
    if tier in _DEV_SKU_TIERS:
        return True
    return any(name.startswith(p) for p in _DEV_SKU_PREFIXES)


def _is_expensive_sku(resource: CloudResource) -> bool:
    name = (resource.sku_name or "").lower()
    if resource.provider == "gcp":
        return name.split("-", 1)[0] in _GCP_EXPENSIVE_FAMILIES
    return any(name.startswith(p) for p in _EXPENSIVE_VM_PREFIXES)


class DevInProdAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "dev_in_prod"

    def analyze(
        self,
        subscription_id: str,
        resources: list[CloudResource],
        costs: list[ResourceCost],
    ) -> list[Finding]:
        findings = []
        for resource in resources:
            rtype = resource.type.lower()
            if rtype not in _CHECK_TYPES.get(resource.provider, set()):
                continue

            env = _env_from_resource(resource)
            is_prod_env = env in _PROD_ENV_VALUES
            is_dev_env = env in _DEV_ENV_VALUES

            if is_prod_env and _is_dev_sku(resource):
                findings.append(Finding(
                    subscription_id=subscription_id,
                    resource_group=resource.resource_group,
                    resource_id=resource.id,
                    resource_type=resource.type,
                    severity=Severity.HIGH,
                    category="DevInProd",
                    estimated_monthly_savings_usd=0.0,
                    recommendation=(
                        f"Recurso en entorno de producción usa SKU de desarrollo/prueba "
                        f"({resource.sku_tier}/{resource.sku_name}). "
                        "Revise si el SKU es adecuado para producción o si el entorno está mal etiquetado."
                    ),
                    metadata={"environment": env, "sku_name": resource.sku_name, "sku_tier": resource.sku_tier},
                    provider=resource.provider,
                ))
            elif is_dev_env and _is_expensive_sku(resource):
                findings.append(Finding(
                    subscription_id=subscription_id,
                    resource_group=resource.resource_group,
                    resource_id=resource.id,
                    resource_type=resource.type,
                    severity=Severity.MEDIUM,
                    category="DevInProd",
                    estimated_monthly_savings_usd=0.0,
                    recommendation=(
                        f"Recurso en entorno de desarrollo/staging usa SKU costoso "
                        f"({resource.sku_name}). "
                        "Considere reducir el SKU para ahorrar costos en ambiente no productivo."
                    ),
                    metadata={"environment": env, "sku_name": resource.sku_name, "sku_tier": resource.sku_tier},
                    provider=resource.provider,
                ))
        return findings
