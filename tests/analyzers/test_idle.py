import pytest
from finops.analyzers.idle import IdleAnalyzer
from finops.config import FinOpsConfig, CostThresholds
from finops.models import Severity
from tests.conftest import make_resource, make_cost


def _config(threshold=0.10):
    return FinOpsConfig(
        subscriptions=[{"id": "sub1", "name": "Test"}],
        cost_thresholds=CostThresholds(idle_resource_daily_usd=threshold),
    )


def test_flags_resource_below_threshold_every_day():
    config = _config(threshold=0.10)
    analyzer = IdleAnalyzer(config)
    resource = make_resource()
    cost = make_cost(resource_id=resource.id, daily_costs={"2026-05-01": 0.05, "2026-05-02": 0.03})
    findings = analyzer.analyze("sub1", [resource], [cost])
    assert len(findings) == 1
    assert findings[0].severity == Severity.MEDIUM
    assert findings[0].category == "Idle"


def test_no_finding_when_cost_exceeds_threshold_any_day():
    config = _config(threshold=0.10)
    analyzer = IdleAnalyzer(config)
    resource = make_resource()
    cost = make_cost(resource_id=resource.id, daily_costs={"2026-05-01": 0.05, "2026-05-02": 5.0})
    findings = analyzer.analyze("sub1", [resource], [cost])
    assert findings == []


def test_no_finding_for_resource_with_no_cost_entry():
    config = _config()
    analyzer = IdleAnalyzer(config)
    resource = make_resource()
    findings = analyzer.analyze("sub1", [resource], [])
    assert findings == []


def test_estimated_savings_equals_total_cost():
    config = _config(threshold=0.10)
    analyzer = IdleAnalyzer(config)
    resource = make_resource()
    cost = make_cost(resource_id=resource.id, daily_costs={"2026-05-01": 0.05, "2026-05-02": 0.05})
    findings = analyzer.analyze("sub1", [resource], [cost])
    assert findings[0].estimated_monthly_savings_usd == pytest.approx(0.10)
