from pathlib import Path
from finops.reporters.models import report_from_json, Report
from finops.reporters.html import HtmlReporter
from finops.models import SubscriptionData, ResourceCost

FIXTURE = Path(__file__).parent / "fixtures" / "data.json"


def _report_no_invoices_monthly_granularity() -> Report:
    sub = SubscriptionData(
        subscription_id="sub-x",
        subscription_name="No Invoice Sub",
        resources=[],
        costs=[
            ResourceCost(
                resource_id="/subscriptions/sub-x/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
                resource_group="rg",
                subscription_id="sub-x",
                resource_type="microsoft.compute/virtualmachines",
                daily_costs={"2026-04-01": 200.0, "2026-03-01": 180.0},
            )
        ],
        invoices=[],
    )
    return Report(
        generated_at="2026-05-07T00:00:00Z",
        date_from="2026-01-01",
        date_to="2026-05-07",
        subscriptions=[sub],
    )


def test_html_report_contains_subscription_name():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    assert "Test Subscription" in html


def test_html_report_contains_total_cost():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    assert "10.00" in html


def test_html_report_contains_finding_category():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    assert "Untagged" in html


def test_html_report_contains_invoice_period():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    assert "202605" in html


def test_html_report_contains_accrual():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    assert "Acumulado" in html


def test_html_report_contains_both_invoices():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    assert "202605" in html
    assert "202604" in html


def test_html_report_shows_outstanding_amount():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    # Outstanding = 1500.00 (inv1 is Due)
    assert "1,500" in html or "1500" in html


def test_html_accrual_shown_with_no_invoices():
    """Accrual must appear even when there are no invoices."""
    html = HtmlReporter().render(_report_no_invoices_monthly_granularity())
    assert "Acumulado" in html


def test_html_accrual_falls_back_to_last_month_when_current_empty():
    """Monthly granularity: date_to=2026-05-07 but no May costs → use April."""
    html = HtmlReporter().render(_report_no_invoices_monthly_granularity())
    assert "2026-04" in html
    assert "200" in html


def test_html_contains_forecast():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    assert "Pronóstico" in html


def test_html_forecast_shown_with_no_invoices():
    html = HtmlReporter().render(_report_no_invoices_monthly_granularity())
    assert "Pronóstico" in html


def test_html_report_is_valid_html():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "</html>" in html
