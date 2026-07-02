"""Reporters must render a GCP subscription (resource_group None/empty, GCP
publisher_type) without raising."""
from finops.reporters.models import Report
from finops.reporters.html import HtmlReporter
from finops.reporters.markdown import MarkdownReporter
from finops.reporters.excel import ExcelReporter
from finops.models import SubscriptionData
from tests.conftest import make_gcp_resource, make_gcp_cost, make_finding


def _gcp_report():
    finding = make_finding(
        subscription_id="my-gcp-project",
        resource_group=None,
        resource_id="//compute.googleapis.com/projects/p/zones/z/instances/vm1",
        resource_type="compute.googleapis.com/instance",
        category="Scheduling",
    )
    finding.provider = "gcp"
    sub = SubscriptionData(
        subscription_id="my-gcp-project",
        subscription_name="GCP Client",
        resources=[make_gcp_resource()],
        costs=[make_gcp_cost(daily_costs={"2026-05-01": 5.0, "2026-05-02": 6.0})],
        invoices=[],
        findings=[finding],
    )
    return Report(
        generated_at="2026-05-06T10:00:00Z", date_from="2026-05-01",
        date_to="2026-05-06", subscriptions=[sub],
    )


def test_html_renders_gcp_report():
    html = HtmlReporter().render(_gcp_report())
    assert "GCP Client" in html


def test_markdown_renders_gcp_report():
    md = MarkdownReporter().render(_gcp_report())
    assert "GCP Client" in md


def test_excel_renders_gcp_report():
    data = ExcelReporter().render(_gcp_report())
    assert isinstance(data, bytes) and len(data) > 0
