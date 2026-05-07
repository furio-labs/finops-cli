import pytest
from unittest.mock import MagicMock
from finops.collectors.invoices import InvoiceCollector
from finops.models import Invoice


def _make_sdk_invoice(
    inv_id="/subscriptions/sub1/providers/Microsoft.Billing/billingPeriods/202605",
    name="202605",
    amount=1500.0,
    currency="USD",
    status="Due",
    due_date="2026-06-15",
    pdf_url="https://portal.azure.com/invoice.pdf",
):
    inv = MagicMock()
    inv.id = inv_id
    inv.name = name
    inv.amount_due = MagicMock()
    inv.amount_due.amount = amount
    inv.amount_due.currency = currency
    inv.status = status
    inv.due_date = due_date
    inv.invoice_pdf = MagicMock()
    inv.invoice_pdf.url = pdf_url
    return inv


def test_invoice_collector_maps_fields(mocker):
    mock_client = MagicMock()
    mocker.patch("finops.collectors.invoices.BillingManagementClient", return_value=mock_client)
    mock_client.invoices.list_by_billing_subscription.return_value = [_make_sdk_invoice()]
    collector = InvoiceCollector(credential=MagicMock())
    results = collector.collect("sub1")
    assert len(results) == 1
    inv = results[0]
    assert inv.billing_period == "202605"
    assert inv.amount_due == 1500.0
    assert inv.currency == "USD"
    assert inv.status == "Due"
    assert inv.pdf_url == "https://portal.azure.com/invoice.pdf"


@pytest.mark.parametrize("status_code", [404, 403, 500])
def test_invoice_collector_returns_empty_on_error(mocker, status_code):
    mock_client = MagicMock()
    mocker.patch("finops.collectors.invoices.BillingManagementClient", return_value=mock_client)
    from azure.core.exceptions import HttpResponseError
    err = HttpResponseError(message="Not supported")
    err.status_code = status_code
    mock_client.invoices.list_by_billing_subscription.side_effect = err
    collector = InvoiceCollector(credential=MagicMock())
    results = collector.collect("sub1")
    assert results == []
