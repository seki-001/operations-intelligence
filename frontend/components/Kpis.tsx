import { delta, fmt } from "@/lib/format";
import type { PeriodMetrics } from "@/lib/types";

type Kpi = {
  label: string;
  value: string;
  prev: string;
  change: ReturnType<typeof delta>;
};

export function Kpis({ cur, prev, missingSiteDays }: { cur: PeriodMetrics; prev: PeriodMetrics; missingSiteDays: number }) {
  // Totals over incomplete data would show a misleading change, so the comparison is withheld.
  const totalChange = (c: number, p: number) =>
    missingSiteDays > 0 ? ({ label: "incomplete", tone: "flat" } as const) : delta(c, p, true, "pct");
  const items: Kpi[] = [
    {
      label: "Energy sold",
      value: fmt.kwh(cur.energy_sold_kwh),
      prev: fmt.kwh(prev.energy_sold_kwh),
      change: totalChange(cur.energy_sold_kwh, prev.energy_sold_kwh),
    },
    {
      label: "Collection rate",
      value: fmt.pct(cur.collection_rate_pct),
      prev: fmt.pct(prev.collection_rate_pct),
      change: delta(cur.collection_rate_pct, prev.collection_rate_pct, true, "pts"),
    },
    {
      label: "Average uptime",
      value: fmt.pct(cur.avg_uptime_pct),
      prev: fmt.pct(prev.avg_uptime_pct),
      change: delta(cur.avg_uptime_pct, prev.avg_uptime_pct, true, "pts"),
    },
    {
      label: "Unsold energy",
      value: fmt.pct(cur.loss_pct),
      prev: fmt.pct(prev.loss_pct),
      change: delta(cur.loss_pct, prev.loss_pct, false, "pts"),
    },
    {
      label: "Revenue collected",
      value: fmt.usd(cur.collected_usd),
      prev: fmt.usd(prev.collected_usd),
      change: totalChange(cur.collected_usd, prev.collected_usd),
    },
  ];

  return (
    <>
    {missingSiteDays > 0 && (
      <p className="note" style={{ margin: "-8px 0 10px" }}>
        {missingSiteDays} site-day{missingSiteDays === 1 ? "" : "s"} in this period had no valid data, so energy and
        revenue totals are understated. Rates and averages use only the valid days.
      </p>
    )}
    <section className="kpis" aria-label="Portfolio indicators">
      {items.map((k) => (
        <div className="kpi" key={k.label}>
          <div className="kpi-label">{k.label}</div>
          <div className="kpi-value num">{k.value}</div>
          <div className="kpi-sub">
            {k.change && <span className={`chg chg-${k.change.tone}`}>{k.change.label}</span>}
            <span>prev {k.prev}</span>
          </div>
        </div>
      ))}
    </section>
    </>
  );
}
