import pytest
from unittest.mock import MagicMock, patch, call
from azure.core.exceptions import HttpResponseError
from finops.collectors.base import retry_on_throttle
from datetime import date
from finops.collectors.cost import CostCollector
from finops.models import ResourceCost


def test_retry_on_throttle_succeeds_first_try():
    fn = MagicMock(return_value="ok")
    result = retry_on_throttle(fn)
    assert result == "ok"
    assert fn.call_count == 1


def test_retry_on_throttle_retries_on_429():
    error_429 = HttpResponseError(message="Too Many Requests")
    error_429.status_code = 429
    fn = MagicMock(side_effect=[error_429, error_429, "ok"])
    with patch("finops.collectors.base.time.sleep") as mock_sleep:
        result = retry_on_throttle(fn, max_retries=3)
    assert result == "ok"
    assert fn.call_count == 3
    assert mock_sleep.call_args_list == [call(5), call(10)]


def test_retry_on_throttle_raises_after_max_retries():
    error_429 = HttpResponseError(message="Too Many Requests")
    error_429.status_code = 429
    fn = MagicMock(side_effect=error_429)
    with patch("finops.collectors.base.time.sleep"):
        with pytest.raises(HttpResponseError):
            retry_on_throttle(fn, max_retries=3)


def _make_query_result(rows, columns=None):
    if columns is None:
        columns = ["Cost", "UsageDate", "ResourceId", "ResourceGroupName", "ResourceType", "Currency"]
    result = MagicMock()
    result.columns = [MagicMock() for _ in columns]
    for i, col in enumerate(result.columns):
        col.name = columns[i]
    result.rows = rows
    return result


def test_cost_collector_returns_resource_costs(mocker):
    mock_client = MagicMock()
    mocker.patch("finops.collectors.cost.CostManagementClient", return_value=mock_client)
    mock_client.query.usage.return_value = _make_query_result([
        [10.0, 20260501, "/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1", "rg-prod", "microsoft.compute/virtualmachines", "USD"],
        [5.0,  20260502, "/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1", "rg-prod", "microsoft.compute/virtualmachines", "USD"],
    ])
    collector = CostCollector(credential=MagicMock())
    results = collector.collect("sub1", date(2026, 5, 1), date(2026, 5, 2))
    assert len(results) == 1
    assert results[0].resource_id == "/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1"
    assert results[0].daily_costs == {"2026-05-01": 10.0, "2026-05-02": 5.0}
    assert results[0].total_cost == 15.0


def test_cost_collector_403_raises_http_error(mocker):
    mock_client = MagicMock()
    mocker.patch("finops.collectors.cost.CostManagementClient", return_value=mock_client)
    error = HttpResponseError(message="Forbidden")
    error.status_code = 403
    mock_client.query.usage.side_effect = error
    collector = CostCollector(credential=MagicMock())
    with pytest.raises(HttpResponseError):
        collector.collect("sub1", date(2026, 5, 1), date(2026, 5, 2))
