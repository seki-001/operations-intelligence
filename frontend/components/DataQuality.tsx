import type { Issue, SyncRun } from "@/lib/types";

export function DataQuality({ issues, snapshot }: { issues: Issue[]; snapshot: SyncRun }) {
  const errors = issues.filter((i) => i.severity === "error").length;
  const warnings = issues.length - errors;

  return (
    <section className="panel section">
      <div className="panel-head">
        <h2>Data quality</h2>
        <span className="hint">
          {snapshot.rows_valid} of {snapshot.rows_read} rows accepted · {errors} rejected · {warnings} flagged
        </span>
      </div>
      {issues.length === 0 ? (
        <div className="panel-body">
          <div className="empty">Every row passed validation.</div>
        </div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th className="left">Sheet row</th>
                <th className="left">Status</th>
                <th className="left">Site</th>
                <th className="left">Field</th>
                <th className="left">Problem</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((i, n) => (
                <tr key={n}>
                  <td className="left num">{i.row}</td>
                  <td className="left">
                    <span className={`sev ${i.severity === "error" ? "sev-critical" : "sev-warning"}`}>
                      {i.severity === "error" ? "Rejected" : "Flagged"}
                    </span>
                  </td>
                  <td className="left">{i.site_id ?? "—"}</td>
                  <td className="left num">{i.field ?? "—"}</td>
                  <td className="left">{i.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
