import pytest
from finops.analyzers.untagged import UntaggedAnalyzer
from finops.config import FinOpsConfig
from finops.models import Severity
from tests.conftest import make_resource, make_cost


def _config(required_tags=None):
    return FinOpsConfig(
        subscriptions=[{"id": "sub1", "name": "Test"}],
        required_tags=required_tags or ["environment", "client", "service"],
    )


def test_flags_resource_missing_all_tags():
    config = _config()
    analyzer = UntaggedAnalyzer(config)
    resource = make_resource(tags={})
    findings = analyzer.analyze("sub1", [resource], [])
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH
    assert findings[0].category == "Untagged"
    assert findings[0].resource_id == resource.id


def test_flags_resource_missing_some_tags():
    config = _config()
    analyzer = UntaggedAnalyzer(config)
    resource = make_resource(tags={"environment": "production"})
    findings = analyzer.analyze("sub1", [resource], [])
    assert len(findings) == 1
    assert "client" in findings[0].metadata["missing_tags"]
    assert "service" in findings[0].metadata["missing_tags"]


def test_no_finding_when_all_tags_present():
    config = _config()
    analyzer = UntaggedAnalyzer(config)
    resource = make_resource(tags={"environment": "production", "client": "acme", "service": "api"})
    findings = analyzer.analyze("sub1", [resource], [])
    assert findings == []


def test_name_property():
    assert UntaggedAnalyzer(_config()).name == "untagged"
