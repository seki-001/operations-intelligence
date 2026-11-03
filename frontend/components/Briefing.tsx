"use client";

import { useState, useTransition } from "react";
import { generateSummary, reviewReport, type ActionResult } from "@/app/actions";
import type { Report } from "@/lib/types";

function Cites({ ids, facts }: { ids: string[]; facts: Report["facts"] }) {
  return (
    <>
      {ids.map((id) => (
        <span key={id} className="cite" title={facts.find((f) => f.id === id)?.text ?? "Unknown fact"}>
          {id}
        </span>
      ))}
    </>
  );
}

export function Briefing({ report, periodDays, snapshotId }: { report: Report | null; periodDays: number; snapshotId: number }) {
  const [pending, start] = useTransition();
  const [result, setResult] = useState<ActionResult | null>(null);
  const [reviewer, setReviewer] = useState("");
  const stale = report && report.sync_run_id !== snapshotId;

  const run = (fn: () => Promise<ActionResult>) => start(async () => setResult(await fn()));

  return (
    <section className="panel brief">
      <div className="panel-head">
        <h2>Briefing</h2>
        <span className="hint">Written only from the cited facts</span>
        <span className="spacer" />
        <button className="btn btn-primary" disabled={pending} onClick={() => run(() => generateSummary(periodDays))}>
          {pending ? "Working…" : report ? "Redraft" : "Draft briefing"}
        </button>
      </div>
      <div className="panel-body">
        {!report && (
          <div className="empty">
            No briefing yet. Drafting one turns the findings into a short summary for leadership. Every draft needs a
            named reviewer before it is shared.
          </div>
        )}

        {report && (
          <>
            <div className="label-row">
              {report.is_ai_generated ? (
                <span className="pill pill-ai">AI draft · {report.model}</span>
              ) : (
                <span className="pill pill-template">Template summary · no AI model used</span>
              )}
              <span className={`pill pill-${report.review_status === "pending_review" ? "pending" : report.review_status}`}>
                {report.review_status === "pending_review"
                  ? "Awaiting review"
                  : `${report.review_status === "approved" ? "Approved" : "Rejected"} by ${report.reviewed_by}`}
              </span>
              {stale && <span className="pill pill-pending">Older data snapshot</span>}
            </div>
            <div className="note">{report.period}</div>
            {report.fallback_reason && <div className="note">Note: {report.fallback_reason}; template used instead.</div>}

            <h3>Observed</h3>
            <ul>
              {report.observations.map((o, i) => (
                <li key={i}>
                  {o.text}
                  <Cites ids={o.fact_ids} facts={report.facts} />
                </li>
              ))}
            </ul>

            {report.hypotheses.length > 0 && (
              <>
                <h3>Possible explanations · not confirmed</h3>
                <ul>
                  {report.hypotheses.map((h, i) => (
                    <li key={i} className="hypo">
                      {h.text}
                      <Cites ids={h.fact_ids} facts={report.facts} />
                    </li>
                  ))}
                </ul>
              </>
            )}

            {report.suggested_checks.length > 0 && (
              <>
                <h3>Suggested checks</h3>
                <ul>
                  {report.suggested_checks.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </>
            )}

            {(report.unverified_numbers.length > 0 || report.unknown_fact_ids.length > 0) && (
              <div className="alert" role="alert">
                Guardrail: this draft contains{" "}
                {report.unverified_numbers.length > 0 && <>numbers not found in the facts ({report.unverified_numbers.join(", ")})</>}
                {report.unverified_numbers.length > 0 && report.unknown_fact_ids.length > 0 && " and "}
                {report.unknown_fact_ids.length > 0 && <>citations to unknown facts ({report.unknown_fact_ids.join(", ")})</>}.
                Check carefully or redraft before approving.
              </div>
            )}

            {report.review_status === "pending_review" && (
              <div className="review">
                <input
                  aria-label="Reviewer name"
                  placeholder="Reviewer name"
                  value={reviewer}
                  onChange={(e) => setReviewer(e.target.value)}
                  maxLength={80}
                />
                <button className="btn btn-good" disabled={pending} onClick={() => run(() => reviewReport(report.id, "approved", reviewer))}>
                  Approve
                </button>
                <button className="btn btn-bad" disabled={pending} onClick={() => run(() => reviewReport(report.id, "rejected", reviewer))}>
                  Reject
                </button>
              </div>
            )}
          </>
        )}
        {result && <div className={`toast ${result.ok ? "toast-ok" : "toast-bad"}`} role="status">{result.message}</div>}
      </div>
    </section>
  );
}
