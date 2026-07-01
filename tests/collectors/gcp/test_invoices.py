from unittest.mock import MagicMock
from finops.collectors.gcp.invoices import InvoiceCollector


def test_gcp_invoices_returns_empty():
    col = InvoiceCollector(MagicMock())
    assert col.collect("my-project") == []
