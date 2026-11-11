"use client";

import Link from "next/link";
import { useState } from "react";

import { DeleteUploadButton } from "@/components/DeleteUploadButton";

import { formatDate } from "@/lib/format";
import { LIFTS } from "@/lib/lifts";
import type { HistoryItem } from "@/lib/types";

export function HistoryList({ items, onDelete }: { items: HistoryItem[]; onDelete?: (uploadId: string) => Promise<void> }) {
  const [lift, setLift] = useState("all");
  const [selection, setSelected] = useState<string[]>([]);
  const selected = selection.filter((id) => items.some((item) => item.analysis_id === id));
  const first = items.find((item) => item.analysis_id === selected[0]);
  const shown = lift === "all" ? items : items.filter((i) => i.lift === lift);

  function toggle(id: string) {
    setSelected(selected.includes(id) ? selected.filter((value) => value !== id) : [...selected, id]);
  }
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm">
        Lift
        <select value={lift} onChange={(e) => { setLift(e.target.value); setSelected([]); }} className="rounded-lg border border-zinc-300 px-2 py-1">
          <option value="all">All</option>
          {LIFTS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
        </select>
      </label>
      {items.length > 0 && <p className="text-sm text-zinc-600">Select two completed uploads of the same lift to compare.</p>}
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
            <label className="mb-3 ml-3 flex w-fit items-center gap-2 text-sm text-zinc-700">
              <input type="checkbox" checked={selected.includes(i.analysis_id)} onChange={() => toggle(i.analysis_id)}
                aria-label={`Select ${i.lift_label} upload from ${formatDate(i.created_at)} for comparison`}
                disabled={i.status !== "done" || !i.final_status || i.final_status === "unanalyzable"
                  || (!selected.includes(i.analysis_id) && (selected.length === 2 || Boolean(first && first.lift !== i.lift)))}
                className="accent-zinc-900 disabled:opacity-40" />
              Compare this upload
            </label>
            {i.upload_id && onDelete && <DeleteUploadButton uploadId={i.upload_id} onDelete={onDelete} />}
          </li>
        ))}
      </ul>
      {items.length > 0 && (selected.length === 2 ? (
        <Link href={`/compare?first=${encodeURIComponent(selected[0])}&second=${encodeURIComponent(selected[1])}`}
          className="inline-block rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white">
          Compare selected uploads
        </Link>
      ) : (
        <button type="button" disabled className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white opacity-40">
          Compare selected uploads
        </button>
      ))}
    </div>
  );
}
