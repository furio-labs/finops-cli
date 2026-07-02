import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

from finops.collectors.aws.resources import ResourceCollector, _type_from_arn
from finops.providers import ProviderPermissionError, ProviderUnavailableError


class _FakeEntry:
    region = "us-east-1"


def _paginator(pages):
    fake = MagicMock()
    fake.paginate.return_value = pages
    return fake


def test_type_from_arn_ec2_instance():
    arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-0abc123"
    assert _type_from_arn(arn) == "ec2:instance"


def test_type_from_arn_rds_db():
    arn = "arn:aws:rds:us-east-1:123456789012:db:mydbinstance"
    assert _type_from_arn(arn) == "rds:db"


def test_collect_returns_cloud_resources():
    credential = MagicMock()
    client = MagicMock()
    credential.client.return_value = client
    client.get_paginator.return_value = _paginator([{
        "ResourceTagMappingList": [{
            "ResourceARN": "arn:aws:ec2:us-east-1:123456789012:instance/i-0abc123",
            "Tags": [{"Key": "environment", "Value": "production"}],
        }],
    }])

    collector = ResourceCollector(credential, _FakeEntry())
    resources = collector.collect("123456789012")

    assert len(resources) == 1
    r = resources[0]
    assert r.id == "arn:aws:ec2:us-east-1:123456789012:instance/i-0abc123"
    assert r.name == "i-0abc123"
    assert r.type == "ec2:instance"
    assert r.provider == "aws"
    assert r.resource_group is None
    assert r.tags == {"environment": "production"}


def test_collect_translates_access_denied_to_permission_error():
    credential = MagicMock()
    client = MagicMock()
    credential.client.return_value = client
    err = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "GetResources")
    client.get_paginator.side_effect = err

    collector = ResourceCollector(credential, _FakeEntry())
    with pytest.raises(ProviderPermissionError):
        collector.collect("123456789012")


def test_collect_translates_other_client_error_to_unavailable():
    credential = MagicMock()
    client = MagicMock()
    credential.client.return_value = client
    err = ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "GetResources")
    client.get_paginator.side_effect = err

    collector = ResourceCollector(credential, _FakeEntry())
    with pytest.raises(ProviderUnavailableError):
        collector.collect("123456789012")
