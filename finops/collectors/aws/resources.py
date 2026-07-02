"""AWS resource collector via the Resource Groups Tagging API
(`get_resources`), the one API that lists resources across every AWS service
in a single paginated call.

It returns ARNs + tags but no SKU/instance-type — that would require a
per-service describe call (EC2 DescribeInstances, RDS DescribeDBInstances,
...) which we intentionally skip for a first pass; `sku_name`/`sku_tier` stay
`None` for AWS and the SKU-aware analyzers (wrong_sku, dev_in_prod) fall back
to type-only heuristics for this provider."""
from __future__ import annotations

from botocore.exceptions import ClientError, BotoCoreError

from finops.models import CloudResource
from finops.providers import ProviderPermissionError, ProviderUnavailableError


def _type_from_arn(arn: str) -> str:
    """`arn:partition:service:region:account:resource-type/resource-id` (or
    `service:resource-type:id`) -> `"service:resource-type"`, lowercased to
    match the other providers' lowercase type strings."""
    parts = arn.split(":", 5)
    if len(parts) < 6:
        return "unknown"
    service = parts[2]
    remainder = parts[5]
    resource_type = remainder.split("/", 1)[0] if "/" in remainder else remainder.split(":", 1)[0]
    return f"{service}:{resource_type}".lower()


class ResourceCollector:
    def __init__(self, credential, entry) -> None:
        self._session = credential
        self._entry = entry
        self._client = credential.client("resourcegroupstaggingapi")

    def collect(self, account_id: str) -> list[CloudResource]:
        results: list[CloudResource] = []
        try:
            paginator = self._client.get_paginator("get_resources")
            for page in paginator.paginate():
                for r in page.get("ResourceTagMappingList", []):
                    arn = r["ResourceARN"]
                    tags = {t["Key"]: t["Value"] for t in r.get("Tags", [])}
                    results.append(CloudResource(
                        id=arn,
                        name=arn.rsplit("/", 1)[-1].rsplit(":", 1)[-1],
                        type=_type_from_arn(arn),
                        subscription_id=account_id,
                        location=self._entry.region,
                        tags=tags,
                        resource_group=None,
                        sku_name=None,
                        sku_tier=None,
                        provider="aws",
                    ))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("AccessDeniedException", "AccessDenied", "UnauthorizedAccess"):
                raise ProviderPermissionError(str(exc)) from exc
            raise ProviderUnavailableError(f"Resource Groups Tagging API error: {exc}") from exc
        except BotoCoreError as exc:
            raise ProviderUnavailableError(f"Resource Groups Tagging API error: {exc}") from exc
        return results
