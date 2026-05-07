from finops.analyzers.scheduling import SchedulingAnalyzer
from finops.config import FinOpsConfig
from finops.models import Severity
from tests.conftest import make_resource, make_cost


def _config():
    return FinOpsConfig(subscriptions=[{"id": "sub1", "name": "Test"}])


def _daily_costs_for_week():
    return {
        "2026-05-01": 1.0, "2026-05-02": 1.0, "2026-05-03": 1.0,
        "2026-05-04": 1.0, "2026-05-05": 1.0, "2026-05-06": 1.0, "2026-05-07": 1.0,
    }


def test_flags_dev_vm_running_all_days():
    analyzer = SchedulingAnalyzer(_config())
    resource = make_resource(
        resource_type="microsoft.compute/virtualmachines",
        tags={"environment": "dev"},
    )
    cost = make_cost(resource_id=resource.id, daily_costs=_daily_costs_for_week())
    findings = analyzer.analyze("sub1", [resource], [cost])
    assert len(findings) == 1
    assert findings[0].category == "Scheduling"
    assert findings[0].severity == Severity.MEDIUM


def test_no_finding_for_production_vm():
    analyzer = SchedulingAnalyzer(_config())
    resource = make_resource(
        resource_type="microsoft.compute/virtualmachines",
        tags={"environment": "production"},
    )
    cost = make_cost(resource_id=resource.id, daily_costs=_daily_costs_for_week())
    findings = analyzer.analyze("sub1", [resource], [cost])
    assert findings == []


def test_no_finding_when_gaps_in_daily_costs():
    analyzer = SchedulingAnalyzer(_config())
    resource = make_resource(
        resource_type="microsoft.compute/virtualmachines",
        tags={"environment": "dev"},
    )
    # Only 5 of 7 days — not running every day
    cost = make_cost(resource_id=resource.id, daily_costs={
        "2026-05-01": 1.0, "2026-05-02": 1.0, "2026-05-03": 1.0,
        "2026-05-05": 1.0, "2026-05-06": 1.0,
    })
    findings = analyzer.analyze("sub1", [resource], [cost])
    assert findings == []


def test_flags_staging_app_service_all_days():
    analyzer = SchedulingAnalyzer(_config())
    resource = make_resource(
        resource_type="microsoft.web/sites",
        tags={"environment": "staging"},
    )
    cost = make_cost(resource_id=resource.id, daily_costs=_daily_costs_for_week())
    findings = analyzer.analyze("sub1", [resource], [cost])
    assert len(findings) == 1
