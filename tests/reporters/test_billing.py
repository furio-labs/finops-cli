"""Unit tests for finops/reporters/billing.py helpers."""
import calendar
from datetime import date
from unittest.mock import patch

import pytest

from finops.reporters.billing import _compute_forecast, _effective_accrual_month
from finops.models import SubscriptionData, ResourceCost


def _sub(daily_costs_list: list[dict[str, float]]) -> SubscriptionData:
    costs = [
        ResourceCost(
            resource_id=f"/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm{i}",
            resource_group="rg",
            subscription_id="s",
            resource_type="microsoft.compute/virtualmachines",
            daily_costs=dc,
        )
        for i, dc in enumerate(daily_costs_list)
    ]
    return SubscriptionData(
        subscription_id="s", subscription_name="Sub",
        resources=[], costs=costs, invoices=[],
    )


# ── _effective_accrual_month ───────────────────────────────────────────────

def test_effective_accrual_month_uses_date_to_when_data_present():
    sub = _sub([{"2026-05-01": 10.0, "2026-05-02": 10.0}])
    assert _effective_accrual_month(sub, "2026-05-07") == "2026-05"


def test_effective_accrual_month_falls_back_to_last_month():
    sub = _sub([{"2026-04-01": 200.0}])  # only April data
    assert _effective_accrual_month(sub, "2026-05-07") == "2026-04"


def test_effective_accrual_month_returns_target_when_no_data():
    sub = _sub([])
    assert _effective_accrual_month(sub, "2026-05-07") == "2026-05"


# ── _compute_forecast ──────────────────────────────────────────────────────

def _mock_today(year: int, month: int, day: int):
    return patch("finops.reporters.billing._date", wraps=date,
                 **{"today.return_value": date(year, month, day)})


def test_forecast_daily_granularity_linear_projection():
    """Current month has day-by-day data → linear extrapolation."""
    # 7 days of data, $10/day; forecast for 31-day month = 310.0
    daily = {f"2026-05-0{d}": 10.0 for d in range(1, 8)}  # May 1-7
    sub = _sub([daily])
    days_in_may = calendar.monthrange(2026, 5)[1]  # 31

    with _mock_today(2026, 5, 8):
        fc = _compute_forecast(sub, "2026-05-07")

    assert fc is not None
    assert fc["forecast"] == pytest.approx(10.0 * days_in_may)
    assert "proyección lineal" in fc["method"]
    assert fc["forecast_month"] == "2026-05"
    assert fc["days_in_month"] == days_in_may


def test_forecast_monthly_granularity_uses_prior_month_rate():
    """No current month data → extrapolate from last complete month."""
    # April total = 300.0 over 30 days → daily rate $10 → May forecast = $310
    sub = _sub([{"2026-04-01": 300.0}])
    days_in_may = calendar.monthrange(2026, 5)[1]

    with _mock_today(2026, 5, 8):
        fc = _compute_forecast(sub, "2026-05-07")

    assert fc is not None
    assert fc["forecast"] == pytest.approx(10.0 * days_in_may)
    assert "basado en" in fc["method"]
    assert "2026-04" in fc["method"]
    assert fc["forecast_month"] == "2026-05"


def test_forecast_returns_none_when_no_cost_data():
    sub = _sub([])
    with _mock_today(2026, 5, 8):
        assert _compute_forecast(sub, "2026-05-07") is None


def test_forecast_days_elapsed_matches_today():
    daily = {f"2026-05-0{d}": 5.0 for d in range(1, 8)}
    sub = _sub([daily])
    with _mock_today(2026, 5, 15):
        fc = _compute_forecast(sub, "2026-05-14")
    assert fc["days_elapsed"] == 15


def test_forecast_multiple_resources_summed():
    """Costs from multiple resources should be summed for the forecast."""
    sub = _sub([
        {"2026-05-01": 10.0, "2026-05-02": 10.0},
        {"2026-05-01": 5.0, "2026-05-02": 5.0},
    ])
    days_in_may = calendar.monthrange(2026, 5)[1]
    with _mock_today(2026, 5, 8):
        fc = _compute_forecast(sub, "2026-05-07")
    # avg $15/day over 2 days × 31 days
    assert fc["forecast"] == pytest.approx(15.0 * days_in_may)
