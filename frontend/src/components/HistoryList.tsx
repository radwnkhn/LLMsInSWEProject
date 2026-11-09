"use client";

import Link from "next/link";
import { useState } from "react";

import { formatDate } from "@/lib/format";
import { LIFTS } from "@/lib/lifts";
import type { HistoryItem } from "@/lib/types";

export function HistoryList({ items }: { items: HistoryItem[] }) {
  const [lift, setLift] = useState("all");
  const shown = lift === "all" ? items : items.filter((i) => i.lift === lift);
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm">
        Lift
        <select value={lift} onChange={(e) => setLift(e.target.value)} className="rounded-lg border border-zinc-300 px-2 py-1">
          <option value="all">All</option>
          {LIFTS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
        </select>
      </label>
      {shown.length === 0 && <p className="text-sm text-zinc-600">{items.length ? "No uploads yet for this lift." : "No uploads yet."}</p>}
      <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200">
        {shown.map((i) => (
          <li key={i.analysis_id}>
            <Link href={`/results/${i.analysis_id}`} className="block px-3 py-3">
              <span className="flex justify-between text-sm text-zinc-500">
                <span>{formatDate(i.created_at)}</span>
                <span>{i.status_label}</span>
              </span>
              <span className="block font-medium">{`${i.lift_label} · ${i.rep_count ?? "–"} reps`}</span>
              {i.top_fix_title && <span className="block text-sm">{i.top_fix_title}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
