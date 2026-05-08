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


import json
import urllib.error
from finops.collectors.cost import _parse_date


def _make_api_response(rows, next_link=None):
    columns = [
        {"name": "Cost", "type": "Number"},
        {"name": "UsageDate", "type": "Number"},
        {"name": "ResourceId", "type": "String"},
        {"name": "ResourceGroupName", "type": "String"},
        {"name": "ResourceType", "type": "String"},
        {"name": "Currency", "type": "String"},
    ]
    return json.dumps({
        "properties": {
            "columns": columns,
            "rows": rows,
            "nextLink": next_link,
        }
    }).encode()


def test_parse_date():
    assert _parse_date(20260501) == "2026-05-01"
    assert _parse_date(20260101) == "2026-01-01"


def test_cost_collector_returns_resource_costs(mocker):
    rows = [
        [10.0, 20260501, "/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1", "rg-prod", "microsoft.compute/virtualmachines", "USD"],
        [5.0,  20260502, "/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1", "rg-prod", "microsoft.compute/virtualmachines", "USD"],
    ]
    mock_cred = MagicMock()
    mock_cred.get_token.return_value.token = "fake-token"

    mocker.patch("finops.collectors.cost._post", return_value={
        "properties": {
            "columns": [
                {"name": "Cost"}, {"name": "UsageDate"}, {"name": "ResourceId"},
                {"name": "ResourceGroupName"}, {"name": "ResourceType"}, {"name": "Currency"},
            ],
            "rows": rows,
            "nextLink": None,
        }
    })

    results = CostCollector(credential=mock_cred).collect("sub1", date(2026, 5, 1), date(2026, 5, 2))
    assert len(results) == 1
    assert results[0].resource_id == "/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1"
    assert results[0].daily_costs == {"2026-05-01": 10.0, "2026-05-02": 5.0}
    assert results[0].total_cost == 15.0


def test_cost_collector_follows_next_link(mocker):
    rid = "/subscriptions/sub1/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1"
    page1_rows = [[3.0, 20260501, rid, "rg", "microsoft.compute/virtualmachines", "USD"]]
    page2_rows = [[7.0, 20260502, rid, "rg", "microsoft.compute/virtualmachines", "USD"]]
    columns = [
        {"name": "Cost"}, {"name": "UsageDate"}, {"name": "ResourceId"},
        {"name": "ResourceGroupName"}, {"name": "ResourceType"}, {"name": "Currency"},
    ]
    mock_cred = MagicMock()
    mock_cred.get_token.return_value.token = "fake-token"

    mock_post = mocker.patch("finops.collectors.cost._post", return_value={
        "properties": {"columns": columns, "rows": page1_rows, "nextLink": "https://next-page"}
    })
    mock_post = mocker.patch("finops.collectors.cost._post", side_effect=[
        {"properties": {"columns": columns, "rows": page1_rows, "nextLink": "https://next-page"}},
        {"properties": {"columns": columns, "rows": page2_rows, "nextLink": None}},
    ])

    results = CostCollector(credential=mock_cred).collect("sub1", date(2026, 5, 1), date(2026, 5, 2))
    assert len(results) == 1
    assert results[0].total_cost == pytest.approx(10.0)
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[1][0][0] == "https://next-page"


def test_cost_collector_raises_on_api_error(mocker):
    mock_cred = MagicMock()
    mock_cred.get_token.return_value.token = "fake-token"
    mocker.patch("finops.collectors.cost._post", side_effect=RuntimeError("Cost Management API 403: Forbidden"))
    with pytest.raises(RuntimeError, match="403"):
        CostCollector(credential=mock_cred).collect("sub1", date(2026, 5, 1), date(2026, 5, 2))
