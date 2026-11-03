"""Generate a SYNTHETIC daily operations dataset for the demo.

All sites, figures and events are invented. The data contains a few deliberate
"stories" (an uptime problem, a collections drop, rising unsold energy) and a few
deliberate data-entry errors, so the validation and reporting features have
something real to find.

Usage:  python scripts/generate_synthetic_data.py [--end 2026-11-01] [--days 84]
Output: data/synthetic_daily_ops.csv  (import this into a Google Sheet tab named daily_ops)
"""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

HEADER = ["date", "site_id", "site_name", "generation_kwh", "energy_sold_kwh", "active_customers",
          "new_connections", "billed_usd", "collected_usd", "uptime_pct", "outage_events", "notes"]

SITES = [  # fictional sites
    ("HIL", "Hillside", 1400),
    ("LAK", "Lakeshore", 2100),
    ("MKT", "Market Town", 1750),
    ("RIV", "Riverside", 950),
]
TARIFF_USD_PER_KWH = 0.32


def generate(end: date, days: int, seed: int = 42) -> list[list[str]]:
    rng = random.Random(seed)
    start = end - timedelta(days=days - 1)
    rows: list[list[str]] = []
    customers = {sid: base for sid, _, base in SITES}

    for i in range(days):
        day = start + timedelta(days=i)
        days_to_end = (end - day).days
        weather = rng.uniform(0.82, 1.08)  # shared cloud cover across the region
        for sid, name, _ in SITES:
            new_conn = rng.choice([0, 0, 1, 1, 2, 3, 4])
            customers[sid] += new_conn
            cust = customers[sid]

            uptime = rng.uniform(97.5, 100.0)
            outages = 0 if uptime > 99.2 else rng.choice([1, 1, 2])
            loss = rng.uniform(0.07, 0.11)
            collection = rng.uniform(0.88, 0.98)

            # Story 1: Lakeshore battery problem in the latest week.
            if sid == "LAK" and days_to_end < 7:
                uptime = rng.uniform(82.0, 91.0)
                outages = rng.choice([2, 3, 4])
            # Story 2: Market Town collections drop in the latest week.
            if sid == "MKT" and days_to_end < 7:
                collection = rng.uniform(0.66, 0.78)
            # Story 3: Riverside unsold energy creeping up over the last two weeks.
            if sid == "RIV" and days_to_end < 14:
                loss = rng.uniform(0.15, 0.21)

            # Downtime reduces what the grid can deliver, so it scales generation (not losses).
            generation = cust * 1.15 * weather * rng.uniform(0.95, 1.05) * (uptime / 100)
            sold = generation * (1 - loss)
            billed = sold * TARIFF_USD_PER_KWH
            collected = billed * collection
            rows.append([day.isoformat(), sid, name, f"{generation:.1f}", f"{sold:.1f}", str(cust),
                         str(new_conn), f"{billed:.2f}", f"{collected:.2f}", f"{uptime:.1f}", str(outages), ""])

    _inject_errors(rows, end)
    return rows


def _inject_errors(rows: list[list[str]], end: date) -> None:
    """Deliberate data-entry problems, each noted in the 'notes' column."""
    def find(site: str, days_before_end: int) -> list[str]:
        target = (end - timedelta(days=days_before_end)).isoformat()
        return next(r for r in rows if r[0] == target and r[1] == site)

    r = find("HIL", 2)
    r[7] = ""
    r[11] = "demo error: billed_usd left blank"
    r = find("RIV", 4)
    r[3] = "-" + r[3]
    r[11] = "demo error: negative generation"
    r = find("MKT", 20)
    r[0] = "31/02/2026"
    r[11] = "demo error: impossible date"
    r = find("HIL", 30)
    r[9] = "104.0"
    r[11] = "demo error: uptime above 100%"
    r = find("LAK", 12)
    r[4] = f"{float(r[3]) * 1.08:.1f}"
    r[11] = "demo warning: sold exceeds generation"
    r = find("MKT", 9)
    r[10] = ""
    r[11] = "demo warning: outage_events blank"
    dup = list(find("RIV", 15))
    dup[11] = "demo error: duplicate row"
    rows.insert(rows.index(find("RIV", 15)) + 1, dup)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 11, 1))
    parser.add_argument("--days", type=int, default=84)
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "synthetic_daily_ops.csv")
    args = parser.parse_args()
    rows = generate(args.end, args.days)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
