"use client";

import { useState, useTransition } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchTrend } from "@/app/actions";
import { SITE_COLORS, shortDate } from "@/lib/format";
import type { Trend } from "@/lib/types";

const METRICS: { key: string; label: string; unit: string }[] = [
  { key: "energy_sold_kwh", label: "Energy sold", unit: "kWh" },
  { key: "uptime_pct", label: "Uptime", unit: "%" },
  { key: "collection_rate_pct", label: "Collection rate", unit: "%" },
  { key: "loss_pct", label: "Unsold energy", unit: "%" },
  { key: "collected_usd", label: "Collected", unit: "USD" },
];

export function TrendChart({ initial, sites }: { initial: Trend; sites: { id: string; name: string }[] }) {
  const [trend, setTrend] = useState(initial);
  const [pending, start] = useTransition();
  const meta = METRICS.find((m) => m.key === trend.metric) ?? METRICS[0];

  const select = (key: string) =>
    start(async () => {
      const next = await fetchTrend(key);
      if (next) setTrend(next);
    });

  return (
    <section className="panel section">
      <div className="panel-head">
        <h2>Daily trend</h2>
        <span className="hint">{meta.unit}, per site</span>
        <span className="spacer" />
        <div className="tabs" role="tablist" aria-label="Metric">
          {METRICS.map((m) => (
            <button key={m.key} role="tab" className="tab" aria-selected={m.key === trend.metric} onClick={() => select(m.key)}>
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-wrap" style={{ opacity: pending ? 0.5 : 1 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={trend.series} margin={{ left: 8, right: 8 }}>
            <CartesianGrid stroke="#ece9e2" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={shortDate}
              tick={{ fontSize: 11, fill: "#7d828a" }}
              tickLine={false}
              axisLine={{ stroke: "#cfcbc1" }}
              minTickGap={28}
            />
            <YAxis tick={{ fontSize: 11, fill: "#7d828a" }} tickLine={false} axisLine={false} width={52} domain={["auto", "auto"]} />
            <Tooltip
              labelFormatter={(l) => shortDate(String(l))}
              contentStyle={{ borderRadius: 8, border: "1px solid #e3e0d8", fontSize: 12 }}
              formatter={(v, name) => [typeof v === "number" ? v.toLocaleString("en-US") : String(v), sites.find((s) => s.id === name)?.name ?? name]}
            />
            {sites.map((s, i) => (
              <Line key={s.id} type="monotone" dataKey={s.id} stroke={SITE_COLORS[i % SITE_COLORS.length]} strokeWidth={1.75} dot={false} connectNulls={false} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="legend">
        {sites.map((s, i) => (
          <span key={s.id}>
            <span className="swatch" style={{ background: SITE_COLORS[i % SITE_COLORS.length] }} />
            {s.name}
          </span>
        ))}
        <span style={{ marginLeft: "auto" }}>Gaps = no valid data for that day</span>
      </div>
    </section>
  );
}
