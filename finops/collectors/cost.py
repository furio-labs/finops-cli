from __future__ import annotations
import json
from datetime import date
import urllib.request
import urllib.error
from finops.models import ResourceCost

_API_VERSION = "2023-11-01"
_BASE_URL = "https://management.azure.com"


def _parse_date(usage_date_int: int) -> str:
    s = str(usage_date_int)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _get_token(credential) -> str:
    return credential.get_token("https://management.azure.com/.default").token


def _post(url: str, body: dict, token: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode(errors="replace")
        raise RuntimeError(f"Cost Management API {exc.code}: {msg}") from exc


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode(errors="replace")
        raise RuntimeError(f"Cost Management API {exc.code}: {msg}") from exc


class CostCollector:
    def __init__(self, credential) -> None:
        self._credential = credential

    def collect(self, subscription_id: str, start_date: date, end_date: date) -> list[ResourceCost]:
        token = _get_token(self._credential)
        url = (
            f"{_BASE_URL}/subscriptions/{subscription_id}"
            f"/providers/Microsoft.CostManagement/query?api-version={_API_VERSION}"
        )
        body = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {"from": start_date.isoformat(), "to": end_date.isoformat()},
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                "grouping": [
                    {"type": "Dimension", "name": "ResourceId"},
                    {"type": "Dimension", "name": "ResourceGroupName"},
                    {"type": "Dimension", "name": "ResourceType"},
                ],
            },
        }

        costs: dict[str, ResourceCost] = {}
        col_index: dict[str, int] = {}
        next_link: str | None = None

        # First page — POST
        data = _post(url, body, token)
        props = data["properties"]

        col_index = {c["name"]: i for i, c in enumerate(props["columns"])}
        required = {"Cost", "UsageDate", "ResourceId", "ResourceGroupName", "ResourceType"}
        missing = required - col_index.keys()
        if missing:
            raise RuntimeError(
                f"Unexpected Cost Management columns. Missing: {missing}. "
                f"Got: {list(col_index)}"
            )

        def _ingest(rows: list) -> None:
            ci, di, ri, rgi, rti = (
                col_index["Cost"], col_index["UsageDate"],
                col_index["ResourceId"], col_index["ResourceGroupName"],
                col_index["ResourceType"],
            )
            for row in rows:
                rid = row[ri]
                day = _parse_date(int(row[di]))
                cost = float(row[ci])
                if rid not in costs:
                    costs[rid] = ResourceCost(
                        resource_id=rid,
                        resource_group=row[rgi],
                        subscription_id=subscription_id,
                        resource_type=row[rti],
                        daily_costs={},
                    )
                costs[rid].daily_costs[day] = costs[rid].daily_costs.get(day, 0.0) + cost

        _ingest(props["rows"])
        next_link = props.get("nextLink")

        # Subsequent pages — POST to nextLink with same body (skiptoken embedded in URL)
        while next_link:
            data = _post(next_link, body, token)
            props = data["properties"]
            _ingest(props["rows"])
            next_link = props.get("nextLink")

        return list(costs.values())
