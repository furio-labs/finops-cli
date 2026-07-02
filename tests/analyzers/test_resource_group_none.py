"""Regression: resources with resource_group=None (GCP) must not crash the
environment-fallback path in scheduling/dev_in_prod, which calls .lower() on it."""
from finops.analyzers.dev_in_prod import DevInProdAnalyzer
from finops.analyzers.scheduling import SchedulingAnalyzer
from finops.config import FinOpsConfig
from tests.conftest import make_resource, make_cost


def _config():
    return FinOpsConfig(subscriptions=[{"id": "sub1", "name": "Test"}])


def test_dev_in_prod_handles_none_resource_group():
    analyzer = DevInProdAnalyzer(_config())
    # Checked type, no environment tag -> forces the resource_group fallback.
    resource = make_resource(
        resource_type="microsoft.compute/virtualmachines",
        resource_group=None,
        tags={},
        sku_name="Standard_B2s",
        sku_tier="Burstable",
    )
    # Must not raise AttributeError; with no resolvable env there is no finding.
    assert analyzer.analyze("sub1", [resource], []) == []


def test_scheduling_handles_none_resource_group():
    analyzer = SchedulingAnalyzer(_config())
    resource = make_resource(
        resource_type="microsoft.compute/virtualmachines",
        resource_group=None,
        tags={},
    )
    cost = make_cost(
        resource_id=resource.id,
        resource_group="",
        daily_costs={f"2026-05-{d:02d}": 5.0 for d in range(1, 8)},
    )
    assert analyzer.analyze("sub1", [resource], [cost]) == []
