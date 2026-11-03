from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from app.services.analytics import compare_periods, daily_trend

END = date(2026, 11, 1)


@dataclass
class R:
    day: date
    site_id: str = "AAA"
    site_name: str = "Alpha"
    generation_kwh: float = 100.0
    energy_sold_kwh: float = 90.0
    active_customers: int = 50
    new_connections: int = 1
    billed_usd: float = 30.0
    collected_usd: float = 27.0
    uptime_pct: float = 99.0
    outage_events: int = 0


def fortnight(**current_overrides):
    """7 'previous' days of normal data, then 7 'current' days with overrides."""
    rows = []
    for i in range(14):
        day = END - timedelta(days=13 - i)
        rows.append(R(day=day, **(current_overrides if i >= 7 else {})))
    return rows


def metrics_of(result, site="AAA"):
    return next(s for s in result["sites"] if s["current"]["site_id"] == site)


def test_totals_and_rates_are_exact():
    result = compare_periods(fortnight())
    cur = metrics_of(result)["current"]
    assert cur["generation_kwh"] == 700.0
    assert cur["energy_sold_kwh"] == 630.0
    assert cur["collection_rate_pct"] == 90.0
    assert cur["loss_pct"] == 10.0
    assert cur["avg_uptime_pct"] == 99.0
    assert cur["new_connections"] == 7
    assert result["current_period"] == {"start": "2026-10-26", "end": "2026-11-01", "days": 7}
    assert result["findings"] == []  # healthy data -> nothing flagged


def test_collection_rate_critical():
    result = compare_periods(fortnight(collected_usd=21.0))  # 70%
    f = [f for f in result["findings"] if f["metric"] == "collection_rate_pct" and f["site_id"] == "AAA"]
    assert f[0]["severity"] == "critical"
    assert f[0]["current"] == 70.0 and f[0]["previous"] == 90.0 and f[0]["change"] == -20.0


def test_uptime_drop_flagged():
    result = compare_periods(fortnight(uptime_pct=85.0, outage_events=2))
    f = next(f for f in result["findings"] if f["metric"] == "avg_uptime_pct" and f["site_id"] == "AAA")
    assert f["severity"] == "critical"
    assert "14 outage events" in f["statement"]


def test_energy_sold_change_flagged():
    result = compare_periods(fortnight(energy_sold_kwh=72.0))  # -20%
    f = next(f for f in result["findings"] if f["metric"] == "energy_sold_kwh" and f["site_id"] == "AAA")
    assert "fell 20.0%" in f["statement"]


def test_missing_days_reported_and_change_rule_suppressed():
    rows = [r for r in fortnight(energy_sold_kwh=72.0) if r.day != END - timedelta(days=2)]  # one current day missing
    result = compare_periods(rows)
    metrics = {f["metric"] for f in result["findings"] if f["site_id"] == "AAA"}
    assert "days_reported" in metrics
    assert "energy_sold_kwh" not in metrics  # incomplete period: comparison would mislead


def test_portfolio_aggregates_sites():
    rows = fortnight() + [R(day=r.day, site_id="BBB", site_name="Beta") for r in fortnight()]
    p = compare_periods(rows)["portfolio"]["current"]
    assert p["generation_kwh"] == 1400.0
    assert p["active_customers"] == 100


def test_empty_input():
    assert compare_periods([])["findings"] == []


def test_daily_trend_and_unknown_metric():
    rows = fortnight()
    series = daily_trend(rows, "collection_rate_pct")
    assert len(series) == 14 and series[0]["AAA"] == 90.0
    with pytest.raises(ValueError):
        daily_trend(rows, "drop_table")
