import pytest
from unittest.mock import MagicMock
from finops.collectors.resources import ResourceCollector
from finops.models import CloudResource


def _make_sdk_resource(
    rid="/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm1",
    name="vm1",
    rtype="Microsoft.Compute/virtualMachines",
    location="chilecentral",
    tags=None,
    sku_name=None,
    sku_tier=None,
):
    r = MagicMock()
    r.id = rid
    r.name = name
    r.type = rtype
    r.location = location
    r.tags = tags
    if sku_name or sku_tier:
        sku = MagicMock()
        sku.name = sku_name
        sku.tier = sku_tier
        r.sku = sku
    else:
        r.sku = None
    return r


def test_resource_collector_maps_fields(mocker):
    mock_client = MagicMock()
    mocker.patch("finops.collectors.resources.ResourceManagementClient", return_value=mock_client)
    mock_client.resources.list.return_value = [
        _make_sdk_resource(tags={"environment": "production"}, sku_name="Standard_LRS", sku_tier="Standard"),
    ]
    collector = ResourceCollector(credential=MagicMock())
    results = collector.collect("sub1")
    assert len(results) == 1
    r = results[0]
    assert r.name == "vm1"
    assert r.resource_group == "rg-prod"
    assert r.tags == {"environment": "production"}
    assert r.sku_name == "Standard_LRS"
    assert r.sku_tier == "Standard"


def test_resource_collector_none_tags_becomes_empty_dict(mocker):
    mock_client = MagicMock()
    mocker.patch("finops.collectors.resources.ResourceManagementClient", return_value=mock_client)
    mock_client.resources.list.return_value = [_make_sdk_resource(tags=None)]
    collector = ResourceCollector(credential=MagicMock())
    results = collector.collect("sub1")
    assert results[0].tags == {}


def test_resource_collector_no_sku(mocker):
    mock_client = MagicMock()
    mocker.patch("finops.collectors.resources.ResourceManagementClient", return_value=mock_client)
    mock_client.resources.list.return_value = [_make_sdk_resource()]
    collector = ResourceCollector(credential=MagicMock())
    results = collector.collect("sub1")
    assert results[0].sku_name is None
    assert results[0].sku_tier is None
