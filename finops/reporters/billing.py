"""Shared billing helpers: accrual month resolution and cost forecasting."""
from __future__ import annotations
import calendar as _calendar
from datetime import date as _date

from finops.models import SubscriptionData


def _effective_accrual_month(sub: SubscriptionData, date_to: str) -> str:
    """Return the billing month to use for accrual.

    With monthly granularity the API skips incomplete months, so date_to's
    month may have no data. Fall back to the most recent month with data.
    """
    target = date_to[:7]
    months_with_data = {day[:7] for c in sub.costs for day in c.daily_costs}
    if target in months_with_data or not months_with_data:
        return target
    return max(months_with_data)


def _compute_forecast(sub: SubscriptionData, report_date_to: str) -> dict | None:
    """Return a full-month cost forecast for the current calendar month.

    Two cases:
    - Daily granularity: current month has real data → linear extrapolation.
    - Monthly granularity: current month absent → use last complete month's
      daily rate × days in current month.

    Returns None when there is no cost data at all.
    """
    today = _date.today()
    forecast_month = today.strftime("%Y-%m")
    days_in_month = _calendar.monthrange(today.year, today.month)[1]

    months_with_data = {day[:7] for c in sub.costs for day in c.daily_costs}
    if not months_with_data:
        return None

    if forecast_month in months_with_data:
        accrual = sum(
            amt
            for c in sub.costs
            for day, amt in c.daily_costs.items()
            if day.startswith(forecast_month)
        )
        days_with_data = len({
            day
            for c in sub.costs
            for day in c.daily_costs
            if day.startswith(forecast_month)
        })
        daily_rate = accrual / days_with_data if days_with_data else 0.0
        forecast = daily_rate * days_in_month
        method = f"proyección lineal ({days_with_data}/{days_in_month} días)"
    else:
        last_month = max(months_with_data)
        last_total = sum(
            amt
            for c in sub.costs
            for day, amt in c.daily_costs.items()
            if day.startswith(last_month)
        )
        last_month_date = _date.fromisoformat(last_month + "-01")
        last_days = _calendar.monthrange(last_month_date.year, last_month_date.month)[1]
        daily_rate = last_total / last_days if last_days else 0.0
        forecast = daily_rate * days_in_month
        method = f"basado en {last_month}"

    return {
        "forecast": forecast,
        "forecast_month": forecast_month,
        "method": method,
        "days_elapsed": today.day,
        "days_in_month": days_in_month,
    }
