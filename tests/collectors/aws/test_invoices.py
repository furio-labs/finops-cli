from unittest.mock import MagicMock

from finops.collectors.aws.invoices import InvoiceCollector


def test_collect_returns_empty_list():
    collector = InvoiceCollector(MagicMock())
    assert collector.collect("123456789012") == []
