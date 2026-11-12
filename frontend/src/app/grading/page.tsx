"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { TrainerForbidden } from "@/components/TrainerForbidden";
import { ApiError, api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { getToken } from "@/lib/session";
import type { TrainerAssignmentItem } from "@/lib/types";

/** US-22: the sets an admin has sent this trainer, newest first. */
export default function GradingPage() {
  const [items, setItems] = useState<TrainerAssignmentItem[] | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  useEffect(() => {
    api.trainerAssignments(getToken()).then((r) => setItems(r.items))
      .catch((err) => setStatus(err instanceof ApiError ? err.status : 0));
  }, []);
  if (status === 403) return <TrainerForbidden />;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Grading</h1>
      <p className="text-sm text-zinc-600">
        Watch each set and record your own top fault first. Our feedback is shown after that, for you to grade.
      </p>
      {status !== null && <p role="alert" className="text-red-700">Couldn&apos;t load your sets. Please refresh to try again.</p>}
      {items && items.length === 0 && <p className="text-zinc-600">Nothing to grade right now.</p>}
      {items && items.length > 0 && (
        <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200">
          {items.map((a) => (
            <li key={a.assignment_id}>
              <Link href={`/grading/${a.assignment_id}`} className="flex items-center justify-between gap-3 p-3">
                <span className="font-medium">{a.lift_label}</span>
                <span className="text-sm text-zinc-600">{a.status_label} · {formatDate(a.assigned_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
