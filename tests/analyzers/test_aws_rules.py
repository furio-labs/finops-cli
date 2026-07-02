from finops.config import FinOpsConfig, AwsEntry, CostThresholds
from finops.analyzers.scheduling import SchedulingAnalyzer
from finops.analyzers.wrong_sku import WrongSkuAnalyzer
from finops.analyzers.dev_in_prod import DevInProdAnalyzer
from tests.conftest import make_aws_resource, make_aws_cost


def _config():
    return FinOpsConfig(
        subscriptions=[AwsEntry(provider="aws", id="123456789012", name="AWS")],
        cost_thresholds=CostThresholds(),
    )


_WEEK_OF_COSTS = {f"2026-05-{d:02d}": 5.0 for d in range(1, 8)}


def test_scheduling_flags_non_prod_ec2_instance():
    resource = make_aws_resource(tags={"environment": "dev"})
    cost = make_aws_cost(resource_id=resource.id, daily_costs=_WEEK_OF_COSTS)
    findings = SchedulingAnalyzer(_config()).analyze("123456789012", [resource], [cost])
    assert len(findings) == 1
    assert findings[0].provider == "aws"


def test_scheduling_ignores_prod_ec2_instance():
    resource = make_aws_resource(tags={"environment": "production"})
    cost = make_aws_cost(resource_id=resource.id, daily_costs=_WEEK_OF_COSTS)
    findings = SchedulingAnalyzer(_config()).analyze("123456789012", [resource], [cost])
    assert findings == []


def test_wrong_sku_has_no_aws_checks_yet():
    resource = make_aws_resource(resource_type="ec2:instance")
    findings = WrongSkuAnalyzer(_config()).analyze("123456789012", [resource], [])
    assert findings == []


def test_dev_in_prod_has_no_aws_checks_yet():
    resource = make_aws_resource(tags={"environment": "production"})
    findings = DevInProdAnalyzer(_config()).analyze("123456789012", [resource], [])
    assert findings == []
