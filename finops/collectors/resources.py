from __future__ import annotations
from azure.mgmt.resource import ResourceManagementClient
from finops.models import AzureResource
from finops.collectors.base import retry_on_throttle


def _extract_resource_group(resource_id: str) -> str:
    parts = resource_id.split("/")
    try:
        idx = [p.lower() for p in parts].index("resourcegroups")
        return parts[idx + 1]
    except (ValueError, IndexError):
        return ""


class ResourceCollector:
    def __init__(self, credential) -> None:
        self._credential = credential

    def collect(self, subscription_id: str) -> list[AzureResource]:
        client = ResourceManagementClient(self._credential, subscription_id)
        raw = retry_on_throttle(lambda: list(client.resources.list()))
        results = []
        for r in raw:
            rid = (r.id or "").lower()
            results.append(AzureResource(
                id=rid,
                name=r.name,
                type=(r.type or "").lower(),
                resource_group=_extract_resource_group(rid),
                subscription_id=subscription_id,
                location=r.location or "",
                tags=dict(r.tags) if r.tags else {},
                sku_name=r.sku.name if r.sku else None,
                sku_tier=r.sku.tier if r.sku else None,
            ))
        return results
