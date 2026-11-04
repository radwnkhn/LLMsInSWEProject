"use client";

import Link from "next/link";
import { useState } from "react";

import { formatDate } from "@/lib/format";
import { LIFTS } from "@/lib/lifts";
import type { AdminRow } from "@/lib/types";

const STATUSES = [
  ["passed_first_try", "Passed first try"],
  ["passed_after_retry", "Passed after retry"],
  ["fallback", "Fallback"],
  ["unanalyzable", "Couldn't analyze"],
] as const;

export function AdminAnalysesTable({ items }: { items: AdminRow[] }) {
  const [lift, setLift] = useState("all");
  const [status, setStatus] = useState("all");
  const rows = items.filter((r) => (lift === "all" || r.lift === lift) && (status === "all" || r.final_status === status));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2">
          Lift
          <select value={lift} onChange={(e) => setLift(e.target.value)} className="rounded-lg border border-zinc-300 px-2 py-1">
            <option value="all">All</option>
            {LIFTS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2">
          Final status
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-zinc-300 px-2 py-1">
            <option value="all">All</option>
            {STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-zinc-500">
            <tr><th className="py-1 pr-3">Date</th><th className="pr-3">User</th><th className="pr-3">Lift</th>
              <th className="pr-3">Attempts</th><th className="pr-3">Final status</th><th /></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.analysis_id} className="border-t border-zinc-200">
                <td className="py-2 pr-3">{formatDate(r.created_at)}</td>
                <td className="pr-3">{r.user_email}</td>
                <td className="pr-3">{r.lift_label}</td>
                <td className="pr-3">{r.attempt_count}</td>
                <td className="pr-3">{r.final_status_label}</td>
                <td><Link href={`/admin/analyses/${r.analysis_id}`} className="underline">Details</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
