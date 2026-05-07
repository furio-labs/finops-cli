from finops.analyzers.dev_in_prod import DevInProdAnalyzer
from finops.config import FinOpsConfig
from finops.models import Severity
from tests.conftest import make_resource


def _config():
    return FinOpsConfig(subscriptions=[{"id": "sub1", "name": "Test"}])


def test_flags_burstable_vm_in_production_rg():
    analyzer = DevInProdAnalyzer(_config())
    resource = make_resource(
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg-prod",
        tags={"environment": "production"},
        sku_name="Standard_B2s",
        sku_tier="Burstable",
    )
    findings = analyzer.analyze("sub1", [resource], [])
    assert len(findings) == 1
    assert findings[0].category == "DevInProd"
    assert findings[0].severity == Severity.HIGH


def test_flags_expensive_vm_in_dev_rg():
    analyzer = DevInProdAnalyzer(_config())
    resource = make_resource(
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg-dev",
        tags={"environment": "dev"},
        sku_name="Standard_D8s_v5",
        sku_tier="Standard",
    )
    findings = analyzer.analyze("sub1", [resource], [])
    assert len(findings) == 1
    assert findings[0].severity == Severity.MEDIUM


def test_no_finding_standard_vm_in_production():
    analyzer = DevInProdAnalyzer(_config())
    resource = make_resource(
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg-prod",
        tags={"environment": "production"},
        sku_name="Standard_D4s_v5",
        sku_tier="Standard",
    )
    findings = analyzer.analyze("sub1", [resource], [])
    assert findings == []


def test_flags_postgresql_burstable_in_prod():
    analyzer = DevInProdAnalyzer(_config())
    resource = make_resource(
        resource_type="microsoft.dbforpostgresql/flexibleservers",
        resource_group="rg-prod",
        tags={"environment": "production"},
        sku_name="Standard_B2ms",
        sku_tier="Burstable",
    )
    findings = analyzer.analyze("sub1", [resource], [])
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH
    assert findings[0].category == "DevInProd"
