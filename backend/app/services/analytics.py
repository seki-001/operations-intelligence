"""Deterministic analytics. Every number shown on the dashboard or given to the AI
summary is calculated here, in code, so it is testable and reproducible.
The language model never does arithmetic."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Iterable, Protocol

# Thresholds are deliberately simple and visible; in a real deployment the
# FP&A and operations leads would own and tune these.
THRESHOLDS = {
    "collection_rate_min": 0.85,
    "collection_rate_critical": 0.75,
    "collection_rate_drop_pts": 5.0,
    "loss_pct_max": 15.0,
    "loss_pct_rise_pts": 3.0,
    "uptime_min": 95.0,
    "uptime_drop_pts": 3.0,
    "energy_sold_change_pct": 15.0,
}

TREND_METRICS = ["generation_kwh", "energy_sold_kwh", "billed_usd", "collected_usd", "uptime_pct",
                 "collection_rate_pct", "loss_pct"]


class Record(Protocol):
    day: date
    site_id: str
    site_name: str
    generation_kwh: float
    energy_sold_kwh: float
    active_customers: int
    new_connections: int
    billed_usd: float
    collected_usd: float
    uptime_pct: float
    outage_events: int


@dataclass
class PeriodMetrics:
    site_id: str
    site_name: str
    start: date
    end: date
    days_expected: int
    days_reported: int
    generation_kwh: float
    energy_sold_kwh: float
    billed_usd: float
    collected_usd: float
    collection_rate_pct: float | None
    loss_pct: float | None
    avg_uptime_pct: float | None
    outage_events: int
    new_connections: int
    active_customers: int | None


@dataclass
class Finding:
    id: str
    site_id: str
    site_name: str
    metric: str
    severity: str  # info | warning | critical
    current: float | None
    previous: float | None
    change: float | None
    unit: str
    statement: str


def _pct(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator * 100, 1) if denominator else None


def period_metrics(records: Iterable[Record], site_id: str, site_name: str, start: date, end: date) -> PeriodMetrics:
    rows = [r for r in records if start <= r.day <= end]
    gen = sum(r.generation_kwh for r in rows)
    sold = sum(r.energy_sold_kwh for r in rows)
    billed = sum(r.billed_usd for r in rows)
    collected = sum(r.collected_usd for r in rows)
    latest = max(rows, key=lambda r: r.day) if rows else None
    return PeriodMetrics(
        site_id=site_id, site_name=site_name, start=start, end=end,
        days_expected=(end - start).days + 1,
        days_reported=len({(r.site_id, r.day) for r in rows}) if site_id != "ALL" else len({r.day for r in rows}),
        generation_kwh=round(gen, 1), energy_sold_kwh=round(sold, 1),
        billed_usd=round(billed, 2), collected_usd=round(collected, 2),
        collection_rate_pct=_pct(collected, billed),
        loss_pct=round(100 - sold / gen * 100, 1) if gen else None,
        avg_uptime_pct=round(sum(r.uptime_pct for r in rows) / len(rows), 1) if rows else None,
        outage_events=sum(r.outage_events for r in rows),
        new_connections=sum(r.new_connections for r in rows),
        active_customers=(sum(r.active_customers for r in rows if r.day == latest.day) if site_id == "ALL"
                          else latest.active_customers) if latest else None,
    )


def compare_periods(records: list[Record], period_days: int = 7, end: date | None = None) -> dict:
    """Compare the latest `period_days` against the equal-length period before it,
    for every site and for the portfolio as a whole."""
    if not records:
        return {"current_period": None, "previous_period": None, "sites": [], "portfolio": None, "findings": []}

    end = end or max(r.day for r in records)
    cur_start = end - timedelta(days=period_days - 1)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    by_site: dict[str, list[Record]] = defaultdict(list)
    names: dict[str, str] = {}
    for r in records:
        by_site[r.site_id].append(r)
        names[r.site_id] = r.site_name

    sites = []
    findings: list[Finding] = []
    for sid in sorted(by_site):
        cur = period_metrics(by_site[sid], sid, names[sid], cur_start, end)
        prev = period_metrics(by_site[sid], sid, names[sid], prev_start, prev_end)
        sites.append({"current": asdict(cur), "previous": asdict(prev)})
        findings.extend(_findings_for(cur, prev))

    portfolio_cur = period_metrics(records, "ALL", "All sites", cur_start, end)
    portfolio_prev = period_metrics(records, "ALL", "All sites", prev_start, prev_end)
    findings.extend(_findings_for(portfolio_cur, portfolio_prev, portfolio=True))

    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (severity_rank[f.severity], f.site_id))
    for i, f in enumerate(findings, start=1):
        f.id = f"F{i}"

    return {
        "current_period": {"start": cur_start.isoformat(), "end": end.isoformat(), "days": period_days},
        "previous_period": {"start": prev_start.isoformat(), "end": prev_end.isoformat(), "days": period_days},
        "portfolio": {"current": asdict(portfolio_cur), "previous": asdict(portfolio_prev)},
        "sites": sites,
        "findings": [asdict(f) for f in findings],
        "thresholds": THRESHOLDS,
    }


def _delta(cur: float | None, prev: float | None) -> float | None:
    return round(cur - prev, 1) if cur is not None and prev is not None else None


def _findings_for(cur: PeriodMetrics, prev: PeriodMetrics, portfolio: bool = False) -> list[Finding]:
    t = THRESHOLDS
    out: list[Finding] = []
    sid, name = cur.site_id, cur.site_name

    def add(metric, severity, c, p, unit, statement):
        out.append(Finding("", sid, name, metric, severity, c, p, _delta(c, p), unit, statement))

    if not portfolio and cur.days_reported < cur.days_expected:
        missing = cur.days_expected - cur.days_reported
        add("days_reported", "warning", cur.days_reported, cur.days_expected, "days",
            f"{name}: {missing} of {cur.days_expected} days {'has' if missing == 1 else 'have'} no valid data this period, "
            f"so its totals are understated.")

    cr, pcr = cur.collection_rate_pct, prev.collection_rate_pct
    if cr is not None:
        if cr < t["collection_rate_critical"] * 100:
            add("collection_rate_pct", "critical", cr, pcr, "%",
                f"{name}: collected {cr}% of billed revenue (below the {t['collection_rate_critical']*100:.0f}% critical line).")
        elif cr < t["collection_rate_min"] * 100:
            add("collection_rate_pct", "warning", cr, pcr, "%",
                f"{name}: collected {cr}% of billed revenue (target {t['collection_rate_min']*100:.0f}%).")
        elif pcr is not None and pcr - cr >= t["collection_rate_drop_pts"]:
            add("collection_rate_pct", "warning", cr, pcr, "%",
                f"{name}: collection rate fell from {pcr}% to {cr}%.")

    lp, plp = cur.loss_pct, prev.loss_pct
    if lp is not None:
        if lp > t["loss_pct_max"]:
            add("loss_pct", "warning", lp, plp, "%",
                f"{name}: {lp}% of generated energy was not sold (threshold {t['loss_pct_max']:.0f}%).")
        elif plp is not None and lp - plp >= t["loss_pct_rise_pts"]:
            add("loss_pct", "info", lp, plp, "%", f"{name}: unsold energy share rose from {plp}% to {lp}%.")

    up, pup = cur.avg_uptime_pct, prev.avg_uptime_pct
    if up is not None:
        if up < t["uptime_min"]:
            add("avg_uptime_pct", "critical" if up < t["uptime_min"] - 5 else "warning", up, pup, "%",
                f"{name}: average uptime {up}% (target {t['uptime_min']:.0f}%), {cur.outage_events} outage events.")
        elif pup is not None and pup - up >= t["uptime_drop_pts"]:
            add("avg_uptime_pct", "warning", up, pup, "%", f"{name}: average uptime fell from {pup}% to {up}%.")

    if prev.energy_sold_kwh and cur.days_reported == cur.days_expected and prev.days_reported == prev.days_expected:
        change_pct = round((cur.energy_sold_kwh - prev.energy_sold_kwh) / prev.energy_sold_kwh * 100, 1)
        if abs(change_pct) >= t["energy_sold_change_pct"]:
            direction = "rose" if change_pct > 0 else "fell"
            add("energy_sold_kwh", "info" if change_pct > 0 else "warning", cur.energy_sold_kwh,
                prev.energy_sold_kwh, "kWh",
                f"{name}: energy sold {direction} {abs(change_pct)}% "
                f"({prev.energy_sold_kwh:,.1f} to {cur.energy_sold_kwh:,.1f} kWh).")
    return out


def daily_trend(records: list[Record], metric: str, site_id: str | None = None) -> list[dict]:
    """Daily series for one metric, per site, plus a portfolio total where it makes sense."""
    if metric not in TREND_METRICS:
        raise ValueError(f"Unknown metric '{metric}'")
    rows = [r for r in records if site_id is None or r.site_id == site_id]
    by_day: dict[date, list[Record]] = defaultdict(list)
    for r in rows:
        by_day[r.day].append(r)

    series = []
    for day in sorted(by_day):
        point: dict = {"date": day.isoformat()}
        for r in by_day[day]:
            point[r.site_id] = _daily_value(metric, [r])
        point["ALL"] = _daily_value(metric, by_day[day])
        series.append(point)
    return series


def _daily_value(metric: str, rows: list[Record]) -> float | None:
    if metric == "uptime_pct":
        return round(sum(r.uptime_pct for r in rows) / len(rows), 1)
    if metric == "collection_rate_pct":
        return _pct(sum(r.collected_usd for r in rows), sum(r.billed_usd for r in rows))
    if metric == "loss_pct":
        gen = sum(r.generation_kwh for r in rows)
        return round(100 - sum(r.energy_sold_kwh for r in rows) / gen * 100, 1) if gen else None
    return round(sum(getattr(r, metric) for r in rows), 2)
