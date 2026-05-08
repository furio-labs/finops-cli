from io import BytesIO
from pathlib import Path

import openpyxl
import pytest

from finops.reporters.models import report_from_json
from finops.reporters.excel import ExcelReporter

FIXTURE = Path(__file__).parent / "fixtures" / "data.json"


@pytest.fixture
def wb():
    report = report_from_json(FIXTURE.read_text())
    raw = ExcelReporter().render(report)
    return openpyxl.load_workbook(BytesIO(raw))


def test_sheet_names_and_order(wb):
    assert wb.sheetnames == ["Summary", "Findings", "Costs by Resource Group", "Invoices"]


# --- Summary ---

def test_summary_headers(wb):
    ws = wb["Summary"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    assert headers == [
        "Subscription", "Total Cost (USD)", "CRITICAL", "HIGH", "MEDIUM", "INFO",
        "Est. Savings/mo (USD)", "Skipped",
    ]


def test_summary_one_row_per_subscription(wb):
    ws = wb["Summary"]
    assert ws.max_row == 2  # header + 1 subscription


def test_summary_values(wb):
    ws = wb["Summary"]
    assert ws["A2"].value == "Acme Test"
    assert ws["B2"].value == pytest.approx(10.0)
    assert ws["D2"].value == 1   # HIGH count
    assert ws["H2"].value is False  # not skipped


# --- Findings ---

def test_findings_headers(wb):
    ws = wb["Findings"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    assert headers == [
        "Subscription", "Resource Group", "Resource", "Type",
        "Severity", "Category", "Est. Savings/mo (USD)", "Recommendation",
    ]


def test_findings_one_row_per_finding(wb):
    ws = wb["Findings"]
    assert ws.max_row == 2  # header + 1 finding


def test_findings_values(wb):
    ws = wb["Findings"]
    assert ws["A2"].value == "Acme Test"
    assert ws["E2"].value == "HIGH"
    assert ws["F2"].value == "Untagged"
    assert ws["H2"].value == "Recurso sin etiquetas requeridas: service."


def test_findings_severity_cell_is_colored(wb):
    ws = wb["Findings"]
    severity_cell = ws["E2"]
    assert severity_cell.fill.patternType == "solid"
    # HIGH → orange FF8C00 (stored as ARGB: FFFF8C00)
    assert severity_cell.fill.fgColor.rgb.upper().endswith("FF8C00")


# --- Costs by Resource Group ---

def test_costs_headers_include_dynamic_months(wb):
    ws = wb["Costs by Resource Group"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    assert headers[0] == "Subscription"
    assert headers[1] == "Resource Group"
    assert "2026-05" in headers
    assert headers[-1] == "Total (USD)"


def test_costs_one_row_per_rg(wb):
    ws = wb["Costs by Resource Group"]
    assert ws.max_row == 2  # header + 1 RG


def test_costs_values(wb):
    ws = wb["Costs by Resource Group"]
    assert ws["A2"].value == "Acme Test"
    assert ws["B2"].value == "rg-prod"
    # Total should be 10.0 (5.0 + 5.0)
    assert ws.cell(2, ws.max_column).value == pytest.approx(10.0)


# --- Invoices ---

def test_invoices_headers(wb):
    ws = wb["Invoices"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    assert headers == [
        "Subscription", "Billing Period", "Amount Due (USD)", "Currency", "Status",
    ]


def test_invoices_one_row_per_invoice(wb):
    ws = wb["Invoices"]
    assert ws.max_row == 2  # header + 1 invoice


def test_invoices_values(wb):
    ws = wb["Invoices"]
    assert ws["A2"].value == "Acme Test"
    assert ws["B2"].value == "202605"
    assert ws["C2"].value == pytest.approx(1500.0)
    assert ws["D2"].value == "USD"
    assert ws["E2"].value == "Due"
