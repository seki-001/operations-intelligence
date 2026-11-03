import { api, safe } from "@/lib/api";
import { dateRange, timeAgo } from "@/lib/format";
import type { Issue, Overview, Report, SyncStatus, Trend } from "@/lib/types";
import { Briefing } from "@/components/Briefing";
import { DataQuality } from "@/components/DataQuality";
import { Findings } from "@/components/Findings";
import { Kpis } from "@/components/Kpis";
import { SiteTable } from "@/components/SiteTable";
import { SyncButton } from "@/components/SyncButton";
import { TrendChart } from "@/components/TrendChart";

export const dynamic = "force-dynamic";

const PERIODS = [7, 28];

function Mark() {
  return (
    <svg className="brand-mark" viewBox="0 0 22 22" aria-hidden>
      <rect x="1" y="1" width="20" height="20" rx="5" fill="#17191c" />
      <circle cx="7" cy="7" r="1.6" fill="#c2410c" />
      <circle cx="11" cy="7" r="1.6" fill="#f6f4ef" opacity=".55" />
      <circle cx="15" cy="7" r="1.6" fill="#f6f4ef" opacity=".55" />
      <circle cx="7" cy="11" r="1.6" fill="#f6f4ef" opacity=".55" />
      <circle cx="11" cy="11" r="1.6" fill="#c2410c" />
      <circle cx="15" cy="11" r="1.6" fill="#f6f4ef" opacity=".55" />
      <circle cx="7" cy="15" r="1.6" fill="#f6f4ef" opacity=".55" />
      <circle cx="11" cy="15" r="1.6" fill="#f6f4ef" opacity=".55" />
      <circle cx="15" cy="15" r="1.6" fill="#c2410c" />
    </svg>
  );
}

export default async function Page({ searchParams }: { searchParams: { period?: string } }) {
  const periodDays = PERIODS.includes(Number(searchParams.period)) ? Number(searchParams.period) : 7;

  const status = await safe(api<SyncStatus>("/api/sync/status"));
  const current = status.data?.current ?? null;
  const latest = status.data?.latest_attempt ?? null;

  const [overview, trend, dq, report] = current
    ? await Promise.all([
        safe(api<Overview>(`/api/overview?period_days=${periodDays}`)),
        safe(api<Trend>("/api/trends?metric=energy_sold_kwh")),
        safe(api<{ issues: Issue[] }>("/api/data-quality")),
        safe(api<Report | null>("/api/reports/latest")),
      ])
    : [null, null, null, null];

  const lastFailed = latest && latest.status === "failed" && latest.id !== current?.id;

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <Mark />
            Operations Intelligence
          </div>
          <span className="tag tag-accent tag-hide-xs">Synthetic demo data</span>
          <span className="spacer" />
          {current && (
            <div className="sync-meta">
              <span>
                <span className={`dot ${lastFailed ? "dot-bad" : "dot-ok"}`} />
                Synced {timeAgo(current.finished_at)}
              </span>
              <span className="hide-sm">
                Snapshot #{current.id} ·{" "}
                {current.source === "google_sheets"
                  ? "Google Sheets"
                  : current.source === "google_sheets_link"
                    ? "Google Sheets (link)"
                    : "CSV"}
              </span>
            </div>
          )}
          <SyncButton />
        </div>
      </header>

      <main className="page">
        {status.error && (
          <div className="banner banner-bad" role="alert">
            Cannot reach the data service: {status.error.message}
          </div>
        )}
        {lastFailed && (
          <div className="banner banner-bad" role="alert">
            The latest sync failed ({latest.error}). Showing the last good snapshot from {timeAgo(current?.finished_at ?? null)}.
          </div>
        )}

        {!status.error && !current && (
          <div className="panel" style={{ padding: 28 }}>
            <h2 style={{ marginTop: 0 }}>No data yet</h2>
            <p style={{ color: "var(--ink-2)", maxWidth: 560 }}>
              Run a sync to read the operations sheet. The connection is read-only: this tool never writes to the source
              sheet. Rows that fail validation are set aside and listed, not silently fixed.
            </p>
          </div>
        )}

        {overview?.data && (
          <>
            <div className="period">
              <div>
                <h1>{dateRange(overview.data.current_period.start, overview.data.current_period.end)}</h1>
                <p>
                  Compared with {dateRange(overview.data.previous_period.start, overview.data.previous_period.end)} ·{" "}
                  {overview.data.sites.length} sites
                </p>
              </div>
              <span className="spacer" />
              <nav className="seg" aria-label="Period">
                {PERIODS.map((p) => (
                  <a key={p} href={`/?period=${p}`} aria-current={p === periodDays}>
                    {p === 7 ? "Week" : "4 weeks"}
                  </a>
                ))}
              </nav>
            </div>

            <Kpis
              cur={overview.data.portfolio.current}
              prev={overview.data.portfolio.previous}
              missingSiteDays={overview.data.sites.reduce(
                (n, s) => n + (s.current.days_expected - s.current.days_reported),
                0,
              )}
            />

            <div className="grid-2">
              <Findings findings={overview.data.findings} />
              <Briefing report={report?.data ?? null} periodDays={periodDays} snapshotId={current!.id} />
            </div>

            {trend?.data && (
              <TrendChart
                initial={trend.data}
                sites={overview.data.sites.map((s) => ({ id: s.current.site_id, name: s.current.site_name }))}
              />
            )}
            <SiteTable sites={overview.data.sites} />
            {dq?.data && <DataQuality issues={dq.data.issues} snapshot={current!} />}
          </>
        )}
        {overview?.error && (
          <div className="banner banner-bad" role="alert">
            Could not load the overview: {overview.error.message}
          </div>
        )}

        <footer className="foot">
          <span>Read-only: never writes to the source sheet or to site systems.</span>
          <span>All figures are calculated in code. Briefings cite them and need human approval.</span>
          <span>Demo built on fictional sites and synthetic data.</span>
        </footer>
      </main>
    </>
  );
}
