import { delta, fmt } from "@/lib/format";
import type { Overview } from "@/lib/types";

const THRESH = { collection: 85, uptime: 95, loss: 15 };

export function SiteTable({ sites }: { sites: Overview["sites"] }) {
  return (
    <section className="panel section">
      <div className="panel-head">
        <h2>Sites</h2>
        <span className="hint">Current period, change vs previous</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Site</th>
              <th>Energy sold</th>
              <th>Collection</th>
              <th>Uptime</th>
              <th>Unsold</th>
              <th>Outages</th>
              <th>Customers</th>
              <th>Days with data</th>
            </tr>
          </thead>
          <tbody>
            {sites.map(({ current: c, previous: p }) => {
              // A total over an incomplete period would show a fake drop, so don't compare it.
              const complete = c.days_reported === c.days_expected && p.days_reported === p.days_expected;
              const sold = complete
                ? delta(c.energy_sold_kwh, p.energy_sold_kwh, true, "pct")
                : ({ label: "incomplete", tone: "bad" } as const);
              const col = delta(c.collection_rate_pct, p.collection_rate_pct, true, "pts");
              const up = delta(c.avg_uptime_pct, p.avg_uptime_pct, true, "pts");
              const loss = delta(c.loss_pct, p.loss_pct, false, "pts");
              return (
                <tr key={c.site_id}>
                  <td>
                    <strong>{c.site_name}</strong>
                    <span className="cell-sub">{c.site_id}</span>
                  </td>
                  <td className="num">
                    {fmt.int(c.energy_sold_kwh)}
                    {sold && <span className={`cell-sub chg-${sold.tone}`} style={{ background: "none" }}>{sold.label}</span>}
                  </td>
                  <td className="num">
                    <span className={(c.collection_rate_pct ?? 100) < THRESH.collection ? "bad-text" : ""}>{fmt.pct(c.collection_rate_pct)}</span>
                    {col && <span className={`cell-sub chg-${col.tone}`} style={{ background: "none" }}>{col.label}</span>}
                  </td>
                  <td className="num">
                    <span className={(c.avg_uptime_pct ?? 100) < THRESH.uptime ? "bad-text" : ""}>{fmt.pct(c.avg_uptime_pct)}</span>
                    {up && <span className={`cell-sub chg-${up.tone}`} style={{ background: "none" }}>{up.label}</span>}
                  </td>
                  <td className="num">
                    <span className={(c.loss_pct ?? 0) > THRESH.loss ? "bad-text" : ""}>{fmt.pct(c.loss_pct)}</span>
                    {loss && <span className={`cell-sub chg-${loss.tone}`} style={{ background: "none" }}>{loss.label}</span>}
                  </td>
                  <td className="num">{fmt.int(c.outage_events)}</td>
                  <td className="num">
                    {fmt.int(c.active_customers)}
                    <span className="cell-sub">+{c.new_connections} new</span>
                  </td>
                  <td className="num">
                    <span className={c.days_reported < c.days_expected ? "bad-text" : ""}>
                      {c.days_reported}/{c.days_expected}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
