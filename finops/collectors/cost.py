from __future__ import annotations
import json
import time
from datetime import date, timedelta
import urllib.request
import urllib.error
from finops.models import ResourceCost

_MAX_DAYS = 365


def _date_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split a date range into chunks of at most _MAX_DAYS days."""
    chunks = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=_MAX_DAYS - 1), end)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    return chunks

_API_VERSION = "2023-11-01"
_BASE_URL = "https://management.azure.com"
_MAX_RETRIES = 8
_PAGE_DELAY = 2  # seconds between pagination requests to avoid rate limits


def _parse_date(usage_date_int: int) -> str:
    s = str(usage_date_int)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _parse_date_value(val) -> str:
    """Handle both integer YYYYMMDD (daily) and ISO string (monthly) date values."""
    if isinstance(val, (int, float)):
        return _parse_date(int(val))
    # ISO string like "2026-01-01T00:00:00" or "2026-01-01"
    return str(val)[:10]


def _get_token(credential) -> str:
    return credential.get_token("https://management.azure.com/.default").token


def _retry_wait(exc: urllib.error.HTTPError, attempt: int) -> int:
    """Return seconds to wait before retrying a 429 response."""
    header = exc.headers.get("Retry-After") or exc.headers.get("retry-after")
    if header:
        try:
            return max(int(header), 1)
        except ValueError:
            pass
    # Exponential backoff starting at 30s: 30, 60, 120, 240, 480 …
    return 30 * (2 ** attempt)


def _request_with_retry(req: urllib.request.Request) -> dict:
    for attempt in range(_MAX_RETRIES):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < _MAX_RETRIES - 1:
                wait = _retry_wait(exc, attempt)
                time.sleep(wait)
                continue
            msg = exc.read().decode(errors="replace")
            raise RuntimeError(f"Cost Management API {exc.code}: {msg}") from exc


def _post(url: str, body: dict, token: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    return _request_with_retry(req)


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    return _request_with_retry(req)


class CostCollector:
    def __init__(self, credential) -> None:
        self._credential = credential

    def collect(
        self,
        subscription_id: str,
        start_date: date,
        end_date: date,
        granularity: str = "Daily",
    ) -> list[ResourceCost]:
        token = _get_token(self._credential)
        url = (
            f"{_BASE_URL}/subscriptions/{subscription_id}"
            f"/providers/Microsoft.CostManagement/query?api-version={_API_VERSION}"
        )
        costs: dict[str, ResourceCost] = {}

        for chunk_start, chunk_end in _date_chunks(start_date, end_date):
            self._collect_chunk(url, subscription_id, chunk_start, chunk_end, token, costs, granularity)

        return list(costs.values())

    def _collect_chunk(
        self,
        url: str,
        subscription_id: str,
        start_date: date,
        end_date: date,
        token: str,
        costs: dict[str, ResourceCost],
        granularity: str = "Daily",
    ) -> None:
        # Monthly granularity uses "BillingMonth" column; Daily uses "UsageDate"
        date_col = "BillingMonth" if granularity == "Monthly" else "UsageDate"

        body = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {"from": start_date.isoformat(), "to": end_date.isoformat()},
            "dataset": {
                "granularity": granularity,
                "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                "grouping": [
                    {"type": "Dimension", "name": "ResourceId"},
                    {"type": "Dimension", "name": "ResourceGroupName"},
                    {"type": "Dimension", "name": "ResourceType"},
                ],
            },
        }

        # First page — POST
        data = _post(url, body, token)
        props = data["properties"]

        col_index = {c["name"]: i for i, c in enumerate(props["columns"])}

        # Date column name varies by granularity; accept whichever the API returned
        actual_date_col = date_col if date_col in col_index else (
            "BillingMonth" if "BillingMonth" in col_index else "UsageDate"
        )
        required = {"Cost", actual_date_col, "ResourceId", "ResourceGroupName", "ResourceType"}
        missing = required - col_index.keys()
        if missing:
            raise RuntimeError(
                f"Unexpected Cost Management columns. Missing: {missing}. "
                f"Got: {list(col_index)}"
            )

        def _ingest(rows: list) -> None:
            ci = col_index["Cost"]
            di = col_index[actual_date_col]
            ri = col_index["ResourceId"]
            rgi = col_index["ResourceGroupName"]
            rti = col_index["ResourceType"]
            for row in rows:
                rid = row[ri]
                day = _parse_date_value(row[di])
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
            time.sleep(_PAGE_DELAY)
            data = _post(next_link, body, token)
            props = data["properties"]
            _ingest(props["rows"])
            next_link = props.get("nextLink")
