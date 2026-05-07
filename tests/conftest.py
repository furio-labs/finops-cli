from datetime import date
from finops.models import (
    AzureResource, ResourceCost, Invoice, Finding, Severity, SubscriptionData
)

def make_resource(
    resource_id="/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1",
    name="vm1",
    resource_type="microsoft.compute/virtualmachines",
    resource_group="rg-prod",
    subscription_id="sub1",
    location="chilecentral",
    tags=None,
    sku_name=None,
    sku_tier=None,
) -> AzureResource:
    return AzureResource(
        id=resource_id,
        name=name,
        type=resource_type,
        resource_group=resource_group,
        subscription_id=subscription_id,
        location=location,
        tags=tags or {},
        sku_name=sku_name,
        sku_tier=sku_tier,
    )

def make_cost(
    resource_id="/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1",
    resource_group="rg-prod",
    subscription_id="sub1",
    resource_type="microsoft.compute/virtualmachines",
    daily_costs=None,
) -> ResourceCost:
    return ResourceCost(
        resource_id=resource_id,
        resource_group=resource_group,
        subscription_id=subscription_id,
        resource_type=resource_type,
        daily_costs=daily_costs or {"2026-05-01": 5.0, "2026-05-02": 5.0},
    )

def make_finding(
    subscription_id="sub1",
    resource_group="rg-prod",
    resource_id="/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1",
    resource_type="microsoft.compute/virtualmachines",
    severity=Severity.HIGH,
    category="Idle",
    estimated_monthly_savings_usd=50.0,
    recommendation="Elimine este recurso.",
) -> Finding:
    return Finding(
        subscription_id=subscription_id,
        resource_group=resource_group,
        resource_id=resource_id,
        resource_type=resource_type,
        severity=severity,
        category=category,
        estimated_monthly_savings_usd=estimated_monthly_savings_usd,
        recommendation=recommendation,
    )
