export type SyncRun = {
  id: number;
  source: string;
  status: "running" | "success" | "failed";
  started_at: string;
  finished_at: string | null;
  rows_read: number;
  rows_valid: number;
  rows_rejected: number;
  warnings: number;
  error: string | null;
};

export type SyncStatus = { current: SyncRun | null; latest_attempt: SyncRun | null };

export type PeriodMetrics = {
  site_id: string;
  site_name: string;
  start: string;
  end: string;
  days_expected: number;
  days_reported: number;
  generation_kwh: number;
  energy_sold_kwh: number;
  billed_usd: number;
  collected_usd: number;
  collection_rate_pct: number | null;
  loss_pct: number | null;
  avg_uptime_pct: number | null;
  outage_events: number;
  new_connections: number;
  active_customers: number | null;
};

export type Finding = {
  id: string;
  site_id: string;
  site_name: string;
  metric: string;
  severity: "info" | "warning" | "critical";
  current: number | null;
  previous: number | null;
  change: number | null;
  unit: string;
  statement: string;
};

export type Overview = {
  snapshot: SyncRun;
  current_period: { start: string; end: string; days: number };
  previous_period: { start: string; end: string; days: number };
  portfolio: { current: PeriodMetrics; previous: PeriodMetrics };
  sites: { current: PeriodMetrics; previous: PeriodMetrics }[];
  findings: Finding[];
};

export type Issue = { row: number; site_id: string | null; field: string | null; severity: "error" | "warning"; message: string };

export type TrendPoint = { date: string } & Record<string, number | string | null>;
export type Trend = { metric: string; metrics_available: string[]; series: TrendPoint[] };

export type Report = {
  id: number;
  sync_run_id: number;
  created_at: string;
  provider: string;
  model: string | null;
  is_ai_generated: boolean;
  period: string;
  observations: { text: string; fact_ids: string[] }[];
  hypotheses: { text: string; fact_ids: string[] }[];
  suggested_checks: string[];
  fallback_reason: string | null;
  unknown_fact_ids: string[];
  unverified_numbers: string[];
  facts: { id: string; text: string; severity?: string }[];
  review_status: "pending_review" | "approved" | "rejected";
  reviewed_by: string | null;
  reviewed_at: string | null;
};
