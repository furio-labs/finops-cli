from pathlib import Path
from finops.reporters.models import report_from_json
from finops.reporters.markdown import MarkdownReporter

FIXTURE = Path(__file__).parent / "fixtures" / "data.json"


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
