const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const fmt = {
  int: (n: number | null | undefined) => (n == null ? "—" : nf0.format(n)),
  one: (n: number | null | undefined) => (n == null ? "—" : nf1.format(n)),
  pct: (n: number | null | undefined) => (n == null ? "—" : `${nf1.format(n)}%`),
  usd: (n: number | null | undefined) => (n == null ? "—" : usd.format(n)),
  kwh: (n: number | null | undefined) => (n == null ? "—" : `${nf0.format(n)} kWh`),
};

export function shortDate(iso: string) {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

export function dateRange(start: string, end: string) {
  const y = end.slice(0, 4);
  return `${shortDate(start)} – ${shortDate(end)} ${y}`;
}

export function timeAgo(iso: string | null) {
  if (!iso) return "—";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  if (h < 24) return `${h} h ago`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/** Change between two values, and whether that direction is good for the business. */
export function delta(cur: number | null, prev: number | null, higherIsBetter: boolean, mode: "pts" | "pct") {
  if (cur == null || prev == null) return null;
  const raw = mode === "pts" ? cur - prev : prev === 0 ? null : ((cur - prev) / prev) * 100;
  if (raw == null) return null;
  const rounded = Math.round(raw * 10) / 10;
  const tone = Math.abs(rounded) < 0.5 ? "flat" : (rounded > 0) === higherIsBetter ? "good" : "bad";
  const sign = rounded > 0 ? "+" : rounded < 0 ? "−" : "±";
  const label = `${sign}${nf1.format(Math.abs(rounded))}${mode === "pts" ? " pts" : "%"}`;
  return { label, tone } as const;
}

export const SITE_COLORS = ["#C2410C", "#0F766E", "#4338CA", "#A16207", "#BE185D", "#15803D"];
