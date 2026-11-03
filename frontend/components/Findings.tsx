import { fmt } from "@/lib/format";
import type { Finding } from "@/lib/types";

function compare(f: Finding) {
  if (f.previous == null || f.current == null || f.metric === "days_reported") return null;
  const v = (n: number) => (f.unit === "%" ? fmt.pct(n) : f.unit === "kWh" ? fmt.kwh(n) : fmt.one(n));
  return `${v(f.previous)} → ${v(f.current)}`;
}

export function Findings({ findings }: { findings: Finding[] }) {
  const sites = findings.filter((f) => f.site_id !== "ALL");
  const portfolio = findings.filter((f) => f.site_id === "ALL");

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Needs attention</h2>
        <span className="hint">Rule-based checks, calculated in code</span>
      </div>
      <div className="panel-body">
        {findings.length === 0 && <div className="empty">No thresholds crossed this period.</div>}
        {[...sites, ...portfolio].map((f) => {
          const [, rest] = f.statement.split(/:\s(.+)/);
          return (
            <div className="finding" key={f.id}>
              <span className="fid">{f.id}</span>
              <div>
                <span className={`sev sev-${f.severity}`}>{f.severity}</span>
                <span className="finding-site">{f.site_name}</span>
                <div className="finding-text">{rest ?? f.statement}</div>
                {compare(f) && <div className="finding-cmp num">{compare(f)}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
