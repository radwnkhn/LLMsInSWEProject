"use client";

import { useId } from "react";

import { formatTime } from "@/lib/format";
import type { RepBreakdownData } from "@/lib/types";

export function RepBreakdown({ breakdown, onSeek }: { breakdown: RepBreakdownData; onSeek: (seconds: number) => void }) {
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="space-y-2">
      <h2 id={titleId} className="text-lg font-semibold">Rep by rep</h2>
      {breakdown.fatigue_note && <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{breakdown.fatigue_note}</p>}
      <ol className="divide-y divide-zinc-200 rounded-xl border border-zinc-200">
        {breakdown.rows.map((row) => (
          <li key={row.rep} aria-label={`Rep ${row.rep}`}>
            <button type="button" data-rep-start={row.start_time} onClick={() => onSeek(row.start_time)}
              className="flex w-full items-start justify-between gap-3 px-3 py-2.5 text-left text-sm">
              <span className="font-medium">Rep {row.rep} <span className="font-normal text-zinc-500">{formatTime(row.start_time)}</span></span>
              <span className="text-right">
                {row.clean
                  ? <span className="text-emerald-700">Clean</span>
                  : row.faults.map((f) => <span key={f} className="block text-red-700">{f}</span>)}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
