import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

from finops.collectors.aws.cost import CostCollector
from finops.providers import ProviderPermissionError, ProviderUnavailableError


class _FakeEntry:
    region = "us-east-1"


def test_collect_groups_cost_by_service():
    credential = MagicMock()
    client = MagicMock()
    credential.client.return_value = client
    client.get_cost_and_usage.return_value = {
        "ResultsByTime": [{
            "TimePeriod": {"Start": "2026-05-01", "End": "2026-05-02"},
            "Groups": [{
                "Keys": ["Amazon Elastic Compute Cloud"],
                "Metrics": {"UnblendedCost": {"Amount": "12.34", "Unit": "USD"}},
            }],
        }],
    }

    collector = CostCollector(credential, _FakeEntry())
    costs = collector.collect("123456789012", "2026-05-01", "2026-05-02", "Daily")

    assert len(costs) == 1
    rc = costs[0]
    assert rc.resource_id == "aws:unattributed/Amazon_Elastic_Compute_Cloud"
    assert rc.daily_costs == {"2026-05-01": 12.34}
    assert rc.provider == "aws"
    assert rc.publisher_type == "AWS"
    credential.client.assert_called_once_with("ce", region_name="us-east-1")


def test_collect_paginates():
    credential = MagicMock()
    client = MagicMock()
    credential.client.return_value = client
    client.get_cost_and_usage.side_effect = [
        {
            "ResultsByTime": [{
                "TimePeriod": {"Start": "2026-05-01", "End": "2026-05-02"},
                "Groups": [{"Keys": ["EC2"], "Metrics": {"UnblendedCost": {"Amount": "1.0", "Unit": "USD"}}}],
            }],
            "NextPageToken": "abc",
        },
        {
            "ResultsByTime": [{
                "TimePeriod": {"Start": "2026-05-02", "End": "2026-05-03"},
                "Groups": [{"Keys": ["EC2"], "Metrics": {"UnblendedCost": {"Amount": "2.0", "Unit": "USD"}}}],
            }],
        },
    ]

    collector = CostCollector(credential, _FakeEntry())
    costs = collector.collect("123456789012", "2026-05-01", "2026-05-03", "Daily")

    assert len(costs) == 1
    assert costs[0].daily_costs == {"2026-05-01": 1.0, "2026-05-02": 2.0}
    assert client.get_cost_and_usage.call_count == 2


def test_collect_translates_access_denied_to_permission_error():
    credential = MagicMock()
    client = MagicMock()
    credential.client.return_value = client
    err = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "GetCostAndUsage")
    client.get_cost_and_usage.side_effect = err

    collector = CostCollector(credential, _FakeEntry())
    with pytest.raises(ProviderPermissionError):
        collector.collect("123456789012", "2026-05-01", "2026-05-02", "Daily")


def test_collect_non_usd_unit_raises_unavailable():
    credential = MagicMock()
    client = MagicMock()
    credential.client.return_value = client
    client.get_cost_and_usage.return_value = {
        "ResultsByTime": [{
            "TimePeriod": {"Start": "2026-05-01", "End": "2026-05-02"},
            "Groups": [{"Keys": ["EC2"], "Metrics": {"UnblendedCost": {"Amount": "1.0", "Unit": "EUR"}}}],
        }],
    }

    collector = CostCollector(credential, _FakeEntry())
    with pytest.raises(ProviderUnavailableError):
        collector.collect("123456789012", "2026-05-01", "2026-05-02", "Daily")
