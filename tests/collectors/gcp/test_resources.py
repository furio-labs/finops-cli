import types
import pytest
from unittest.mock import MagicMock, patch
from google.api_core import exceptions as gexc

from finops.collectors.gcp.resources import ResourceCollector, _extract_sku
from finops.providers import ProviderPermissionError, ProviderUnavailableError


def _asset(name, asset_type, location="us-central1-a", labels=None, versioned=None):
    return types.SimpleNamespace(
        name=name,
        asset_type=asset_type,
        location=location,
        labels=labels or {},
        versioned_resources=[
            types.SimpleNamespace(resource=v) for v in (versioned or [])
        ],
    )


def _collector_with(results):
    with patch("finops.collectors.gcp.resources.asset_v1.AssetServiceClient") as cls:
        client = cls.return_value
        client.search_all_resources.return_value = iter(results)
        col = ResourceCollector(MagicMock())
    return col, client


def test_maps_compute_instance_to_cloud_resource():
    asset = _asset(
        "//compute.googleapis.com/projects/p/zones/z/instances/vm1",
        "compute.googleapis.com/Instance",
        labels={"environment": "production"},
        versioned=[{"machineType": "https://www.googleapis.com/.../machineTypes/e2-standard-4"}],
    )
    col, client = _collector_with([asset])
    with patch("finops.collectors.gcp.resources.asset_v1.SearchAllResourcesRequest"):
        client.search_all_resources.return_value = iter([asset])
        out = col.collect("my-project")
    assert len(out) == 1
    r = out[0]
    assert r.id == "//compute.googleapis.com/projects/p/zones/z/instances/vm1"
    assert r.name == "vm1"
    assert r.type == "compute.googleapis.com/Instance"
    assert r.subscription_id == "my-project"
    assert r.resource_group is None
    assert r.tags == {"environment": "production"}
    assert r.sku_name == "e2-standard-4"
    assert r.sku_tier == "e2"
    assert r.provider == "gcp"


def test_resource_without_machine_type_has_none_sku():
    asset = _asset(
        "//storage.googleapis.com/projects/p/buckets/b1",
        "storage.googleapis.com/Bucket",
        versioned=[{"location": "US"}],
    )
    col, client = _collector_with([asset])
    with patch("finops.collectors.gcp.resources.asset_v1.SearchAllResourcesRequest"):
        client.search_all_resources.return_value = iter([asset])
        out = col.collect("my-project")
    assert out[0].sku_name is None
    assert out[0].sku_tier is None


def test_permission_denied_raises_permission_error():
    col, client = _collector_with([])
    client.search_all_resources.side_effect = gexc.PermissionDenied("nope")
    with patch("finops.collectors.gcp.resources.asset_v1.SearchAllResourcesRequest"):
        with pytest.raises(ProviderPermissionError):
            col.collect("my-project")


def test_api_error_raises_unavailable():
    col, client = _collector_with([])
    client.search_all_resources.side_effect = gexc.ServiceUnavailable("down")
    with patch("finops.collectors.gcp.resources.asset_v1.SearchAllResourcesRequest"):
        with pytest.raises(ProviderUnavailableError):
            col.collect("my-project")


def test_extract_sku_cloud_sql_tier():
    result = types.SimpleNamespace(
        asset_type="sqladmin.googleapis.com/Instance",
        versioned_resources=[types.SimpleNamespace(resource={"settings": {"tier": "db-n1-standard-4"}})],
    )
    assert _extract_sku(result) == ("db-n1-standard-4", None)
