"""GCP resource collector via Cloud Asset Inventory (search_all_resources).

Machine type / tier live in `versioned_resources`, which is NOT returned by
default — the read_mask must request it, or wrong_sku/dev_in_prod get no SKU to
work with. Every resource's `id` is the Asset full resource name
(`//service/…`); the cost collector must join on exactly this string."""
from __future__ import annotations
from typing import Optional

from google.cloud import asset_v1
from google.protobuf.field_mask_pb2 import FieldMask
from google.api_core import exceptions as gexc

from finops.models import CloudResource
from finops.providers import ProviderPermissionError, ProviderUnavailableError

_READ_MASK_PATHS = [
    "name", "asset_type", "project", "location", "labels",
    "versioned_resources", "additional_attributes",
]


def _struct_to_dict(struct) -> dict:
    if struct is None:
        return {}
    if isinstance(struct, dict):
        return struct
    try:
        from google.protobuf.json_format import MessageToDict
        return MessageToDict(getattr(struct, "_pb", struct))
    except Exception:
        try:
            return dict(struct)
        except Exception:
            return {}


def _extract_sku(result) -> tuple[Optional[str], Optional[str]]:
    """Best-effort (sku_name, sku_tier) from versioned_resources. (None, None)
    when the resource type carries no machine type / tier."""
    asset_type = (getattr(result, "asset_type", "") or "").lower()
    try:
        for vr in getattr(result, "versioned_resources", None) or []:
            res = _struct_to_dict(getattr(vr, "resource", None))
            if not res:
                continue
            machine_type = res.get("machineType")           # Compute Engine
            if machine_type:
                name = str(machine_type).rsplit("/", 1)[-1]  # e2-standard-4
                return name, name.split("-", 1)[0]           # family: e2
            settings = res.get("settings")                   # Cloud SQL
            if isinstance(settings, dict) and settings.get("tier"):
                return str(settings["tier"]), None
            if "disk" in asset_type and res.get("type"):     # Persistent Disk
                return str(res["type"]).rsplit("/", 1)[-1], None
    except Exception:
        pass
    return None, None


class ResourceCollector:
    def __init__(self, credential) -> None:
        self._client = asset_v1.AssetServiceClient(credentials=credential)

    def collect(self, project_id: str) -> list[CloudResource]:
        request = asset_v1.SearchAllResourcesRequest(
            scope=f"projects/{project_id}",
            read_mask=FieldMask(paths=_READ_MASK_PATHS),
        )
        try:
            raw = list(self._client.search_all_resources(request=request))
        except (gexc.PermissionDenied, gexc.Forbidden) as exc:
            raise ProviderPermissionError(str(exc)) from exc
        except gexc.GoogleAPICallError as exc:
            raise ProviderUnavailableError(f"Asset Inventory error: {exc}") from exc

        results = []
        for r in raw:
            sku_name, sku_tier = _extract_sku(r)
            results.append(CloudResource(
                id=r.name,
                name=r.name.rsplit("/", 1)[-1],
                type=r.asset_type,
                subscription_id=project_id,
                location=r.location or "",
                tags=dict(r.labels) if r.labels else {},
                resource_group=None,
                sku_name=sku_name,
                sku_tier=sku_tier,
                provider="gcp",
            ))
        return results
