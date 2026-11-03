"use server";

import { revalidatePath } from "next/cache";
import { api, ApiError } from "@/lib/api";
import type { Trend } from "@/lib/types";

export type ActionResult = { ok: boolean; message: string };

const errorMessage = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong.");

export async function syncNow(): Promise<ActionResult> {
  try {
    const r = await api<{ attempt: { status: string; rows_valid: number; rows_rejected: number; error: string | null } }>(
      "/api/sync",
      { method: "POST" },
    );
    revalidatePath("/");
    return r.attempt.status === "success"
      ? { ok: true, message: `Synced: ${r.attempt.rows_valid} rows accepted, ${r.attempt.rows_rejected} rejected.` }
      : { ok: false, message: `Sync failed: ${r.attempt.error}. Still showing the last good data.` };
  } catch (e) {
    return { ok: false, message: errorMessage(e) };
  }
}

export async function generateSummary(periodDays: number): Promise<ActionResult> {
  try {
    await api("/api/reports/summary", { method: "POST", body: JSON.stringify({ period_days: periodDays }) });
    revalidatePath("/");
    return { ok: true, message: "Briefing drafted. It needs review before it is shared." };
  } catch (e) {
    return { ok: false, message: errorMessage(e) };
  }
}

export async function reviewReport(id: number, decision: "approved" | "rejected", reviewer: string): Promise<ActionResult> {
  const name = reviewer.trim();
  if (name.length < 2) return { ok: false, message: "Enter the reviewer's name." };
  try {
    await api(`/api/reports/${id}/review`, { method: "POST", body: JSON.stringify({ decision, reviewer: name }) });
    revalidatePath("/");
    return { ok: true, message: decision === "approved" ? "Approved." : "Rejected." };
  } catch (e) {
    return { ok: false, message: errorMessage(e) };
  }
}

const METRICS = new Set([
  "generation_kwh", "energy_sold_kwh", "billed_usd", "collected_usd", "uptime_pct", "collection_rate_pct", "loss_pct",
]);

export async function fetchTrend(metric: string): Promise<Trend | null> {
  if (!METRICS.has(metric)) return null;
  try {
    return await api<Trend>(`/api/trends?metric=${encodeURIComponent(metric)}`);
  } catch {
    return null;
  }
}
