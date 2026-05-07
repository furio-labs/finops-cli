import pytest
from finops.models import ResourceCost, Severity, SubscriptionData
from tests.conftest import make_resource, make_cost, make_finding


def test_resource_cost_total():
    cost = make_cost(daily_costs={"2026-05-01": 3.0, "2026-05-02": 2.0})
    assert cost.total_cost == 5.0


def test_resource_cost_avg_daily():
    cost = make_cost(daily_costs={"2026-05-01": 4.0, "2026-05-02": 2.0})
    assert cost.avg_daily_cost == 3.0


def test_subscription_data_total_cost():
    costs = [
        make_cost(daily_costs={"2026-05-01": 10.0}),
        make_cost(daily_costs={"2026-05-01": 5.0}),
    ]
    sub = SubscriptionData(
        subscription_id="sub1",
        subscription_name="Test",
        resources=[],
        costs=costs,
        invoices=[],
    )
    assert sub.total_cost == 15.0


def test_severity_ordering():
    assert Severity.CRITICAL > Severity.HIGH
    assert Severity.HIGH > Severity.MEDIUM
    assert Severity.MEDIUM > Severity.INFO
