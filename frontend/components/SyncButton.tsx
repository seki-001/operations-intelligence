"use client";

import { useState, useTransition } from "react";
import { syncNow, type ActionResult } from "@/app/actions";

export function SyncButton() {
  const [pending, start] = useTransition();
  const [result, setResult] = useState<ActionResult | null>(null);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      {result && (
        <span className={`toast hide-sm ${result.ok ? "toast-ok" : "toast-bad"}`} style={{ margin: 0 }} role="status">
          {result.message}
        </span>
      )}
      <button
        className="btn"
        disabled={pending}
        onClick={() => start(async () => setResult(await syncNow()))}
        title="Read the latest rows from the source sheet (read-only)"
      >
        {pending ? "Syncing…" : "Sync now"}
      </button>
    </div>
  );
}
