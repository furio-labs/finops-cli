import types
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from google.api_core import exceptions as gexc

from finops.collectors.gcp.cost import CostCollector, _canonical_id
from finops.config import GcpEntry
from finops.providers import ProviderPermissionError, ProviderUnavailableError


def _entry():
    return GcpEntry(
        provider="gcp", id="my-project", name="P",
        billing_account_id="0123AB-4567CD-89EF01",
        billing_export_dataset="billing_export",
    )


def _row(resource_key, day, cost, service="Compute Engine", resource_name=None, currency="USD"):
    return types.SimpleNamespace(
        resource_key=resource_key, resource_name=resource_name,
        service_name=service, currency=currency, day=day, cost=cost,
    )


def _collector_with(rows):
    with patch("finops.collectors.gcp.cost.bigquery.Client") as cls:
        client = cls.return_value
        client.query_and_wait.return_value = iter(rows)
        col = CostCollector(MagicMock(), _entry())
    return col, client


def _collect(col, client, rows):
    client.query_and_wait.return_value = iter(rows)
    return col.collect("my-project", date(2026, 5, 1), date(2026, 5, 31))


def test_builds_per_resource_daily_costs():
    rid = "//compute.googleapis.com/projects/p/zones/z/instances/vm1"
    rows = [_row(rid, "2026-05-01", 3.0), _row(rid, "2026-05-02", 4.0)]
    col, client = _collector_with(rows)
    out = _collect(col, client, rows)
    assert len(out) == 1
    rc = out[0]
    assert rc.resource_id == rid
    assert rc.provider == "gcp"
    assert rc.publisher_type == "GCP"
    assert rc.daily_costs == {"2026-05-01": 3.0, "2026-05-02": 4.0}
    assert rc.total_cost == pytest.approx(7.0)


def test_rows_without_global_name_bucketed_unattributable():
    rows = [_row(None, "2026-05-01", 2.0, resource_name="short-name")]
    col, client = _collector_with(rows)
    out = _collect(col, client, rows)
    assert len(out) == 1
    assert out[0].resource_id.startswith("//billing/my-project/unattributed/")


def test_non_usd_currency_raises_unavailable():
    rows = [_row("//x/y", "2026-05-01", 2.0, currency="EUR")]
    col, client = _collector_with(rows)
    with pytest.raises(ProviderUnavailableError):
        _collect(col, client, rows)


def test_missing_table_raises_unavailable():
    col, client = _collector_with([])
    client.query_and_wait.side_effect = gexc.NotFound("no table")
    with pytest.raises(ProviderUnavailableError):
        col.collect("my-project", date(2026, 5, 1), date(2026, 5, 31))


def test_permission_denied_raises_permission_error():
    col, client = _collector_with([])
    client.query_and_wait.side_effect = gexc.PermissionDenied("nope")
    with pytest.raises(ProviderPermissionError):
        col.collect("my-project", date(2026, 5, 1), date(2026, 5, 31))


def test_monthly_granularity_uses_month_start_keys():
    rid = "//compute.googleapis.com/projects/p/zones/z/instances/vm1"
    # Simulate what BigQuery FORMAT_DATE('%Y-%m-01', ...) would return.
    rows = [_row(rid, "2026-05-01", 10.0)]
    col, client = _collector_with(rows)
    client.query_and_wait.return_value = iter(rows)
    out = col.collect("my-project", date(2026, 5, 1), date(2026, 5, 31), granularity="Monthly")
    assert list(out[0].daily_costs.keys()) == ["2026-05-01"]


def test_canonical_id_prefers_full_name():
    assert _canonical_id("//svc/x", "x", "p", "S") == "//svc/x"
    assert _canonical_id(None, None, "p", "Compute Engine") == "//billing/p/unattributed/Compute_Engine"
