from finops.analyzers.wrong_sku import WrongSkuAnalyzer
from finops.config import FinOpsConfig
from finops.models import Severity
from tests.conftest import make_resource, make_cost


def _config():
    return FinOpsConfig(subscriptions=[{"id": "sub1", "name": "Test"}])


def test_flags_premium_storage_account():
    config = _config()
    analyzer = WrongSkuAnalyzer(config)
    resource = make_resource(
        resource_type="microsoft.storage/storageaccounts",
        sku_name="Premium_LRS",
        sku_tier="Premium",
    )
    findings = analyzer.analyze("sub1", [resource], [])
    assert len(findings) == 1
    assert findings[0].category == "WrongSku"
    assert findings[0].severity == Severity.MEDIUM


def test_no_finding_for_standard_storage():
    config = _config()
    analyzer = WrongSkuAnalyzer(config)
    resource = make_resource(
        resource_type="microsoft.storage/storageaccounts",
        sku_name="Standard_LRS",
        sku_tier="Standard",
    )
    findings = analyzer.analyze("sub1", [resource], [])
    assert findings == []


def test_flags_postgresql_business_critical():
    config = _config()
    analyzer = WrongSkuAnalyzer(config)
    resource = make_resource(
        resource_type="microsoft.dbforpostgresql/flexibleservers",
        sku_name="Standard_D4s_v3",
        sku_tier="BusinessCritical",
    )
    findings = analyzer.analyze("sub1", [resource], [])
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH


def test_no_finding_for_postgresql_general_purpose():
    config = _config()
    analyzer = WrongSkuAnalyzer(config)
    resource = make_resource(
        resource_type="microsoft.dbforpostgresql/flexibleservers",
        sku_name="Standard_D2s_v3",
        sku_tier="GeneralPurpose",
    )
    findings = analyzer.analyze("sub1", [resource], [])
    assert findings == []
