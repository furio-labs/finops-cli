from pathlib import Path
from finops.reporters.models import report_from_json, Report
from finops.reporters.markdown import MarkdownReporter
from finops.models import SubscriptionData, ResourceCost

FIXTURE = Path(__file__).parent / "fixtures" / "data.json"


def _report_no_invoices_monthly_granularity() -> Report:
    """Simulates a monthly-granularity run: date_to is current month but
    the API only returned complete months, so costs stop at prior month."""
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


def test_markdown_contains_subscription_name():
    report = report_from_json(FIXTURE.read_text())
    md = MarkdownReporter().render(report)
    assert "Test Subscription" in md


def test_markdown_contains_h1_title():
    report = report_from_json(FIXTURE.read_text())
    md = MarkdownReporter().render(report)
    assert md.startswith("# FinOps Report")


def test_markdown_contains_findings_table():
    report = report_from_json(FIXTURE.read_text())
    md = MarkdownReporter().render(report)
    assert "| Severidad |" in md
    assert "Untagged" in md


def test_markdown_contains_invoice_section():
    report = report_from_json(FIXTURE.read_text())
    md = MarkdownReporter().render(report)
    assert "202605" in md


def test_markdown_contains_ai_insights_section():
    report = report_from_json(FIXTURE.read_text())
    md = MarkdownReporter().render(report)
    assert "Análisis IA" in md
    assert "VMs sobredimensionadas" in md


def test_markdown_contains_accrual():
    report = report_from_json(FIXTURE.read_text())
    md = MarkdownReporter().render(report)
    assert "Acumulado mes actual" in md
    assert "16.00" in md


def test_markdown_contains_outstanding():
    report = report_from_json(FIXTURE.read_text())
    md = MarkdownReporter().render(report)
    assert "Facturas pendientes" in md
    assert "1500.00" in md


def test_markdown_contains_both_invoice_periods():
    report = report_from_json(FIXTURE.read_text())
    md = MarkdownReporter().render(report)
    assert "202605" in md
    assert "202604" in md


def test_markdown_accrual_shown_with_no_invoices():
    """Accrual must appear even when there are no invoices."""
    md = MarkdownReporter().render(_report_no_invoices_monthly_granularity())
    assert "Acumulado mes actual" in md


def test_markdown_accrual_falls_back_to_last_month_when_current_empty():
    """With monthly granularity date_to=2026-05-07 but no May costs,
    accrual should use the most recent month with data (2026-04)."""
    md = MarkdownReporter().render(_report_no_invoices_monthly_granularity())
    assert "2026-04" in md
    assert "200.00" in md


def test_markdown_contains_forecast():
    report = report_from_json(FIXTURE.read_text())
    md = MarkdownReporter().render(report)
    assert "Pronóstico" in md


def test_markdown_forecast_shown_with_no_invoices():
    """Forecast must appear even when subscription has no invoice history."""
    md = MarkdownReporter().render(_report_no_invoices_monthly_granularity())
    assert "Pronóstico" in md
