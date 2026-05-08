from pathlib import Path
from finops.reporters.models import report_from_json
from finops.reporters.html import HtmlReporter

FIXTURE = Path(__file__).parent / "fixtures" / "data.json"


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


def test_html_report_is_valid_html():
    report = report_from_json(FIXTURE.read_text())
    html = HtmlReporter().render(report)
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "</html>" in html
