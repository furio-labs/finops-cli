from finops.models import (
    CloudResource, ResourceCost, Invoice, Finding, Severity, SubscriptionData
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
    provider="azure",
) -> CloudResource:
    return CloudResource(
        id=resource_id,
        name=name,
        type=resource_type,
        resource_group=resource_group,
        subscription_id=subscription_id,
        location=location,
        tags=tags or {},
        sku_name=sku_name,
        sku_tier=sku_tier,
        provider=provider,
    )

def make_cost(
    resource_id="/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1",
    resource_group="rg-prod",
    subscription_id="sub1",
    resource_type="microsoft.compute/virtualmachines",
    daily_costs=None,
    provider="azure",
) -> ResourceCost:
    return ResourceCost(
        resource_id=resource_id,
        resource_group=resource_group,
        subscription_id=subscription_id,
        resource_type=resource_type,
        daily_costs=daily_costs or {"2026-05-01": 5.0, "2026-05-02": 5.0},
        provider=provider,
    )

def make_gcp_resource(
    resource_id="//compute.googleapis.com/projects/p/zones/z/instances/vm1",
    name="vm1",
    resource_type="compute.googleapis.com/instance",
    subscription_id="my-gcp-project",
    location="us-central1-a",
    tags=None,
    sku_name="e2-standard-4",
    sku_tier="e2",
) -> CloudResource:
    return make_resource(
        resource_id=resource_id, name=name, resource_type=resource_type,
        resource_group=None, subscription_id=subscription_id, location=location,
        tags=tags, sku_name=sku_name, sku_tier=sku_tier, provider="gcp",
    )


def make_gcp_cost(
    resource_id="//compute.googleapis.com/projects/p/zones/z/instances/vm1",
    subscription_id="my-gcp-project",
    resource_type="Compute Engine",
    daily_costs=None,
) -> ResourceCost:
    return make_cost(
        resource_id=resource_id, resource_group="", subscription_id=subscription_id,
        resource_type=resource_type, daily_costs=daily_costs, provider="gcp",
    )


def make_aws_resource(
    resource_id="arn:aws:ec2:us-east-1:123456789012:instance/i-0abc123",
    name="i-0abc123",
    resource_type="ec2:instance",
    subscription_id="123456789012",
    location="us-east-1",
    tags=None,
) -> CloudResource:
    return make_resource(
        resource_id=resource_id, name=name, resource_type=resource_type,
        resource_group=None, subscription_id=subscription_id, location=location,
        tags=tags, sku_name=None, sku_tier=None, provider="aws",
    )


def make_aws_cost(
    resource_id="aws:unattributed/Amazon_Elastic_Compute_Cloud",
    subscription_id="123456789012",
    resource_type="Amazon Elastic Compute Cloud",
    daily_costs=None,
) -> ResourceCost:
    return make_cost(
        resource_id=resource_id, resource_group="", subscription_id=subscription_id,
        resource_type=resource_type, daily_costs=daily_costs, provider="aws",
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
