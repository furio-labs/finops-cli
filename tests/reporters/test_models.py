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
