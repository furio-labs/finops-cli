import pytest
from finops.reporters.models import Report, report_to_json, report_from_json
from finops.models import Severity, SubscriptionData, Invoice
from tests.conftest import make_resource, make_cost, make_finding


def _make_report():
    finding = make_finding()
    sub = SubscriptionData(
        subscription_id="sub1",
        subscription_name="Test Subscription",
        resources=[make_resource()],
        costs=[make_cost()],
        invoices=[Invoice(
            id="inv1", name="202605", subscription_id="sub1",
            billing_period="202605", amount_due=1500.0, currency="USD",
            status="Due",
        )],
        findings=[finding],
    )
    return Report(
        generated_at="2026-05-06T10:00:00Z",
        date_from="2026-05-01",
        date_to="2026-05-06",
        subscriptions=[sub],
    )


def test_report_total_cost():
    report = _make_report()
    assert report.total_cost == pytest.approx(10.0)


def test_report_total_savings():
    report = _make_report()
    assert report.total_estimated_savings == 50.0


def test_report_all_findings():
    report = _make_report()
    assert len(report.all_findings) == 1


def test_report_roundtrip_json():
    report = _make_report()
    json_str = report_to_json(report)
    restored = report_from_json(json_str)
    assert restored.date_from == "2026-05-01"
    assert len(restored.subscriptions) == 1
    assert restored.subscriptions[0].findings[0].severity == Severity.HIGH
    assert restored.subscriptions[0].findings[0].estimated_monthly_savings_usd == 50.0


def test_report_roundtrip_preserves_provider():
    sub = SubscriptionData(
        subscription_id="my-gcp-project",
        subscription_name="GCP Project",
        resources=[make_resource(subscription_id="my-gcp-project", resource_group=None, provider="gcp")],
        costs=[make_cost(subscription_id="my-gcp-project", resource_group="", provider="gcp")],
        invoices=[],
    )
    report = Report(
        generated_at="2026-05-06T10:00:00Z", date_from="2026-05-01",
        date_to="2026-05-06", subscriptions=[sub],
    )
    restored = report_from_json(report_to_json(report))
    r = restored.subscriptions[0]
    assert r.resources[0].provider == "gcp"
    assert r.resources[0].resource_group is None
    assert r.costs[0].provider == "gcp"


def test_from_dict_legacy_json_without_provider_field():
    """Pre-GCP data.json has no `provider` key; it must still deserialize (default azure)."""
    legacy = {
        "generated_at": "2026-05-06T10:00:00Z",
        "date_from": "2026-05-01",
        "date_to": "2026-05-06",
        "subscriptions": [
            {
                "subscription_id": "sub1",
                "subscription_name": "Legacy Azure",
                "resources": [
                    {
                        "id": "/subscriptions/sub1/resourceGroups/rg/providers/x/vm1",
                        "name": "vm1", "type": "microsoft.compute/virtualmachines",
                        "resource_group": "rg", "subscription_id": "sub1",
                        "location": "chilecentral", "tags": {},
                        "sku_name": None, "sku_tier": None,
                    }
                ],
                "costs": [
                    {
                        "resource_id": "/subscriptions/sub1/resourceGroups/rg/providers/x/vm1",
                        "resource_group": "rg", "subscription_id": "sub1",
                        "resource_type": "microsoft.compute/virtualmachines",
                        "daily_costs": {"2026-05-01": 5.0},
                        "publisher_type": "Azure", "service_name": "",
                    }
                ],
                "invoices": [],
                "findings": [
                    {
                        "subscription_id": "sub1", "resource_group": "rg",
                        "resource_id": "/subscriptions/sub1/resourceGroups/rg/providers/x/vm1",
                        "resource_type": "microsoft.compute/virtualmachines",
                        "severity": "HIGH", "category": "Idle",
                        "estimated_monthly_savings_usd": 50.0,
                        "recommendation": "Elimine este recurso.", "metadata": {},
                    }
                ],
            }
        ],
    }
    import json
    restored = report_from_json(json.dumps(legacy))
    sub = restored.subscriptions[0]
    assert sub.resources[0].provider == "azure"
    assert sub.costs[0].provider == "azure"
    assert sub.findings[0].provider == "azure"
    assert sub.resources[0].resource_group == "rg"
